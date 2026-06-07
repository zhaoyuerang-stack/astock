"""
每日生产入口 run_daily.py

流程：①增量更新数据 → ②质量校验 → ③生成择时信号 → ④持仓清单
      → ⑤调仓判断(距上次≥20交易日) → ⑥保存 signals/YYYY-MM-DD.json

策略: illiquidity v1.0 (Amihud 非流动性因子 + PureTrend MA16 择时)
      18候选并行探索唯一全流程通过者, WF +35.6%, 真实盘 +20.0%

用法：python3 run_daily.py            # 完整流程(含联网更新数据)
      python3 run_daily.py --no-update # 跳过数据更新，仅用现有数据出信号
"""
import warnings; warnings.filterwarnings("ignore")
import os, json, argparse
from pathlib import Path
from datetime import date
os.chdir(Path(__file__).parent)
import numpy as np
import pandas as pd

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from core.backtest import (
    load_price_panels,
    small_cap_timing,
    build_rebalance_weights,
)
from factors.utils import safe_zscore, mad_clip
from factors.market_stress import HMMStressConfig, build_market_features, latest_hmm_stress
from lake.validator import DataValidator
from app_config.settings import get_settings

_cfg = get_settings().strategy
_hmm_cfg = get_settings().hmm_stress

SIGNALS = Path("signals"); SIGNALS.mkdir(exist_ok=True)
LAST_REBAL = SIGNALS / "_last_rebalance.txt"
STATE_FILE = SIGNALS / "state.json"

# illiquidity v1.0 参数
TOP_N = _cfg.top_n
TIMING_MA = _cfg.timing_ma
REBAL_DAYS = _cfg.rebalance_days
LEVERAGE = _cfg.leverage
ILLIQ_WINDOW = 20
START = get_settings().data.warmup_start


def load_state():
    default = {
        "current_position": "cash",
        "last_rebalance_date": None,
        "last_signal_date": None,
        "last_holdings": [],
    }
    if STATE_FILE.exists():
        return {**default, **json.loads(STATE_FILE.read_text())}
    if LAST_REBAL.exists():
        default["last_rebalance_date"] = LAST_REBAL.read_text().strip()
    return default


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    if state.get("last_rebalance_date"):
        LAST_REBAL.write_text(state["last_rebalance_date"])
    elif LAST_REBAL.exists():
        LAST_REBAL.unlink()


def decide_action(trade_dates, last_date, in_market, state):
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
    print(f"  每日运行  {date.today()}  —  illiquidity v1.0")
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
    last = close.index[-1]
    cal = pd.read_parquet("data_lake/meta/trade_calendar.parquet")["date"]
    v = DataValidator(calendar=cal)
    sample = ["600519", "000001", "300750", "600036", "601398"]
    bad = [c for c in sample if c in close.columns
           and not v.validate(c, pd.read_parquet(f"data_lake/price/daily/{c}.parquet"))["ok"]]
    print(f"  最新交易日: {last.date()} | 抽样校验: {'✅全部通过' if not bad else f'⚠️{bad}异常'}")

    # ③ 择时信号 + illiquidity 因子
    print("\n[3/6] 生成择时信号 (illiquidity + PureTrend MA16)...")
    # illiquidity factor: Amihud |ret|/amount, rolling 20d
    ret_abs = close.pct_change(fill_method=None).abs().replace([float('inf'), float('-inf')], float('nan'))
    illiq_raw = (ret_abs / (amount + 1)).rolling(ILLIQ_WINDOW, min_periods=10).mean()
    factor = safe_zscore(mad_clip(illiq_raw))

    # PureTrend MA16 timing (shared with v2.0, proven)
    timing_raw, small_nav, timing_dist = small_cap_timing(close, amount, TIMING_MA)
    dist = float(timing_dist.loc[last]) if last in timing_dist.index else 0.0
    base_in_market = bool(timing_raw.loc[last])

    # HMM stress guard (optional)
    stress_info = {"prob_stress": 0.0, "stress_state": None, "cache_key": None}
    stress_block = False
    if _hmm_cfg.enabled:
        market_features = build_market_features(close, amount)
        stress_info = latest_hmm_stress(
            market_features, target_date=last,
            cfg=HMMStressConfig(
                lookback=_hmm_cfg.lookback, retrain_days=_hmm_cfg.retrain_days,
                threshold=_hmm_cfg.threshold, max_iter=_hmm_cfg.max_iter,
                filter_days=_hmm_cfg.filter_days,
            ),
        )
        stress_block = stress_info["prob_stress"] > _hmm_cfg.threshold

    in_market = bool(base_in_market and not stress_block)
    print(f"  小盘指数 vs MA{TIMING_MA}: {dist:+.2%} → {'🟢持仓' if base_in_market else '🔴空仓观望'}")
    if _hmm_cfg.enabled:
        print(f"  HMM压力: {stress_info['prob_stress']:.2%} / 阈值{_hmm_cfg.threshold:.0%} → "
              f"{'🔴风控空仓' if stress_block else '🟢通过'}")

    # ④ 持仓清单
    print("\n[4/6] 持仓清单...")
    f = factor.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(TOP_N).index.tolist()

    # ⑤ 调仓判断
    print("\n[5/6] 调仓判断...")
    state = load_state()
    is_rebal, reason, action = decide_action(close.index, last, in_market, state)
    if stress_block:
        reason = f"HMM压力 {stress_info['prob_stress']:.2%} > {_hmm_cfg.threshold:.0%}，风控空仓"
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
        "hmm_stress_enabled": bool(_hmm_cfg.enabled),
        "hmm_stress_prob": round(float(stress_info["prob_stress"]), 6),
        "hmm_stress_threshold": float(_hmm_cfg.threshold),
        "hmm_stress_block": bool(stress_block),
        "is_execution_day": is_rebal,
        "is_rebalance_day": bool(is_rebal and in_market),
        "rebalance_reason": reason,
        "action": action,
        "holdings": holdings if in_market else [],
        "top_n": TOP_N, "leverage": LEVERAGE,
        "strategy": "illiquidity", "strategy_version": "v1.0",
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
    print(f"  策略      : illiquidity v1.0 (Amihud 非流动性)")
    print(f"  日期      : {last.date()}")
    print(f"  择时      : {signal['timing']}  (小盘指数{dist:+.2%} vs MA{TIMING_MA})")
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
