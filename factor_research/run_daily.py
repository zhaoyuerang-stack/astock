"""
每日生产入口 run_daily.py —— 把研究脚本收敛成一个明确的生产流程

流程：①增量更新数据 → ②质量校验 → ③生成择时信号 → ④持仓清单
      → ⑤调仓判断(距上次≥20交易日) → ⑥保存 signals/YYYY-MM-DD.json

用法：python3 run_daily.py            # 完整流程(含联网更新数据)
      python3 run_daily.py --no-update # 跳过数据更新，仅用现有数据出信号
"""
import warnings; warnings.filterwarnings("ignore")
import os, json, argparse
from pathlib import Path
from datetime import date
os.chdir(Path(__file__).parent)
import pandas as pd

# Phase-2: use unified BacktestEngine instead of legacy core.backtest
from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from core.backtest import (
    load_price_panels,
    small_cap_factor,
    small_cap_timing,
    build_rebalance_weights,
)
from factors.market_stress import HMMStressConfig, build_market_features, latest_hmm_stress
from core.overlays import PureTrendOverlay
from lake.validator import DataValidator
from app_config.settings import get_settings

_cfg = get_settings().strategy
_hmm_cfg = get_settings().hmm_stress

SIGNALS = Path("signals"); SIGNALS.mkdir(exist_ok=True)
LAST_REBAL = SIGNALS / "_last_rebalance.txt"
STATE_FILE = SIGNALS / "state.json"

# 策略参数（从 config/settings.py 读取，默认与 v2.0 一致）
TOP_N = _cfg.top_n
TIMING_MA = _cfg.timing_ma
REBAL_DAYS = _cfg.rebalance_days
LEVERAGE = _cfg.leverage
SIZE_WINDOW = _cfg.size_window
START = get_settings().data.warmup_start


def load_state():
    """读取账户状态；兼容旧版仅有 _last_rebalance.txt 的状态文件。"""
    default = {
        "current_position": "cash",      # cash / invested
        "last_rebalance_date": None,
        "last_signal_date": None,
        "last_holdings": [],
    }
    if STATE_FILE.exists():
        return {**default, **json.loads(STATE_FILE.read_text())}
    if LAST_REBAL.exists():
        # 旧状态无法判断是否仍持仓，保守视为空仓，不让空仓日阻止后续建仓。
        default["last_rebalance_date"] = LAST_REBAL.read_text().strip()
    return default


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    if state.get("last_rebalance_date"):
        LAST_REBAL.write_text(state["last_rebalance_date"])
    elif LAST_REBAL.exists():
        LAST_REBAL.unlink()


def decide_action(trade_dates, last_date, in_market, state):
    """根据择时和真实持仓状态决定是否建仓/调仓/清仓/维持。"""
    position = state.get("current_position", "cash")

    if not in_market:
        if position == "invested":
            return True, "择时转空，清仓", "清仓"
        return False, "当前空仓且择时为空，继续观望", "空仓观望"

    if position != "invested":
        return True, "择时转多，当前无持仓，建仓", "建仓买入"

    last_rebal_raw = state.get("last_rebalance_date")
    if not last_rebal_raw:
        return True, "持仓状态缺少上次调仓日，重新调仓", "调仓买入"

    last_rebal = pd.Timestamp(last_rebal_raw)
    gap = int(((trade_dates > last_rebal) & (trade_dates <= last_date)).sum())
    if gap >= REBAL_DAYS:
        return True, f"距上次调仓 {gap} 交易日 (≥{REBAL_DAYS})", "调仓买入"
    return False, f"距上次调仓 {gap} 交易日 (<{REBAL_DAYS})，维持原仓位", "维持原仓位"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-update", action="store_true")
    args = ap.parse_args()

    print("=" * 60)
    print(f"  每日运行  {date.today()}")
    print("=" * 60)

    # ① 增量更新数据
    if not args.no_update:
        print("\n[1/6] 增量更新价量数据...")
        try:
            from scripts.data import update_lake
            update_lake.update_prices()
        except Exception as e:
            print(f"  ⚠️ 更新失败({str(e)[:50]})，用现有数据继续")
    else:
        print("\n[1/6] 跳过数据更新(--no-update)")

    # ② 加载 + 质量校验
    print("\n[2/6] 加载数据 + 质量校验...")
    close, volume, amount = load_price_panels(START)
    prices = PricePanel(close=close, volume=volume, amount=amount)
    last = close.index[-1]
    cal = pd.read_parquet("data_lake/meta/trade_calendar.parquet")["date"]
    v = DataValidator(calendar=cal)
    # 抽样校验5只主力股
    sample = ["600519", "000001", "300750", "600036", "601398"]
    bad = [c for c in sample if c in close.columns
           and not v.validate(c, pd.read_parquet(f"data_lake/price/daily/{c}.parquet"))["ok"]]
    print(f"  最新交易日: {last.date()} | 抽样校验: {'✅全部通过' if not bad else f'⚠️{bad}异常'}")

    # ③ 择时信号
    print("\n[3/6] 生成择时信号...")
    factor = small_cap_factor(amount, SIZE_WINDOW)
    timing, _, _ = small_cap_timing(close, amount, TIMING_MA)
    # Recalculate dist directly (same as small_cap_timing returns)
    ret = close.pct_change(fill_method=None).replace([float('inf'), float('-inf')], float('nan'))
    small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
    small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
    small_nav = (1 + small_idx.fillna(0)).cumprod()
    dist = small_nav.iloc[-1] / small_nav.iloc[-TIMING_MA:].mean() - 1
    base_in_market = bool(timing.loc[last])

    # Pure Trend overlay (tw=2, WF validated 12/12 years, Sharpe 3.40 vs HMM 2.23)
    _pt = PureTrendOverlay(trend_window=2)
    pure_trend_block = _pt.signal(last, close) == 0.0
    mkt_ret_2d = ret.mean(axis=1).fillna(0.0).rolling(2).sum()
    pure_trend_val = float(mkt_ret_2d.loc[last]) if last in mkt_ret_2d.index else 0.0

    # HMM overlay (optional, kept for reference)
    stress_info = {"prob_stress": 0.0, "stress_state": None, "cache_key": None}
    stress_block = False
    if _hmm_cfg.enabled:
        market_features = build_market_features(close, amount)
        stress_info = latest_hmm_stress(
            market_features,
            target_date=last,
            cfg=HMMStressConfig(
                lookback=_hmm_cfg.lookback,
                retrain_days=_hmm_cfg.retrain_days,
                threshold=_hmm_cfg.threshold,
                max_iter=_hmm_cfg.max_iter,
                filter_days=_hmm_cfg.filter_days,
            ),
        )
        stress_block = stress_info["prob_stress"] > _hmm_cfg.threshold

    in_market = bool(base_in_market and not pure_trend_block and not stress_block)
    print(f"  小盘指数 vs MA{TIMING_MA}: {dist:+.2%} → {'🟢持仓' if base_in_market else '🔴空仓观望'}")
    pt_verdict = "🔴风控空仓" if pure_trend_block else "🟢通过"
    print(f"  纯趋势 tw=2: 2日累计={pure_trend_val:+.3%} → {pt_verdict}")
    if _hmm_cfg.enabled:
        verdict = "风控空仓" if stress_block else "通过"
        print(f"  HMM流动性压力: {stress_info['prob_stress']:.2%} / 阈值{_hmm_cfg.threshold:.0%} → {verdict}")

    # ④ 持仓清单
    print("\n[4/6] 持仓清单...")
    f = factor.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(TOP_N).index.tolist()

    # ⑤ 调仓判断
    print("\n[5/6] 调仓判断...")
    state = load_state()
    is_rebal, reason, action = decide_action(close.index, last, in_market, state)
    if pure_trend_block or stress_block:
        if pure_trend_block and stress_block:
            reason = f"纯趋势tw2={pure_trend_val:+.3%}<0 & HMM压力{stress_info['prob_stress']:.2%}，风控空仓"
        elif pure_trend_block:
            reason = f"纯趋势tw2={pure_trend_val:+.3%}<0，风控空仓"
        else:
            reason = f"HMM流动性压力 {stress_info['prob_stress']:.2%} > {_hmm_cfg.threshold:.0%}，风控空仓"
        action = "清仓" if state.get("current_position") == "invested" else "空仓观望"
        is_rebal = state.get("current_position") == "invested"
    print(f"  {'🔄 今日执行' if is_rebal else '⏸ 不执行'} — {reason}")

    # ⑥ 保存 signals
    print("\n[6/6] 保存信号...")
    signal = {
        "date": str(last.date()),
        "timing": "持仓" if in_market else "空仓",
        "in_market": in_market,
        "base_in_market": base_in_market,
        "small_index_vs_ma16": round(float(dist), 4),
        "pure_trend_tw2": round(pure_trend_val, 6),
        "pure_trend_block": bool(pure_trend_block),
        "hmm_stress_enabled": bool(_hmm_cfg.enabled),
        "hmm_stress_prob": round(float(stress_info["prob_stress"]), 6),
        "hmm_stress_threshold": float(_hmm_cfg.threshold),
        "hmm_stress_block": bool(stress_block),
        "hmm_stress_state": stress_info["stress_state"],
        "is_execution_day": is_rebal,
        "is_rebalance_day": bool(is_rebal and in_market),
        "rebalance_reason": reason,
        "action": action,
        "holdings": holdings if in_market else [],
        "top_n": TOP_N, "leverage": LEVERAGE,
        "strategy_version": "v2.0+pt2",
    }
    out = SIGNALS / f"{last.date()}.json"
    out.write_text(json.dumps(signal, ensure_ascii=False, indent=2))

    new_state = {
        "current_position": "invested" if in_market else "cash",
        "last_rebalance_date": (
            str(last.date()) if (is_rebal and in_market)
            else state.get("last_rebalance_date") if in_market
            else None
        ),
        "last_signal_date": str(last.date()),
        "last_holdings": holdings if in_market else [],
        "last_action": action,
    }
    save_state(new_state)

    # ── 终端总结 ──
    print("\n" + "=" * 60)
    print(f"  日期      : {last.date()}")
    print(f"  择时      : {signal['timing']}  (小盘指数{dist:+.2%} vs MA16)")
    print(f"  纯趋势tw2 : {'空仓' if pure_trend_block else '持仓'}  (2日累计{pure_trend_val:+.3%})")
    if _hmm_cfg.enabled:
        print(f"  HMM压力   : {stress_info['prob_stress']:.2%} / 阈值{_hmm_cfg.threshold:.0%}")
    print(f"  执行      : {'是' if is_rebal else '否'} — {reason}")
    print(f"  操作      : {signal['action']}")
    if in_market:
        print(f"  持仓({len(holdings)}只): {', '.join(holdings[:12])}{' ...' if len(holdings)>12 else ''}")
    print(f"  已保存    : {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
