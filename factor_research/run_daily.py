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
from datetime import datetime
from zoneinfo import ZoneInfo
os.chdir(Path(__file__).parent)
CHINA_TZ = ZoneInfo("Asia/Shanghai")
import numpy as np
import pandas as pd

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from core.backtest import (
    load_price_panels,
    small_cap_timing,
    build_rebalance_weights,
)
from lake.validator import DataValidator
from factors.alpha import transforms  # register zscore/mad_clip/shift
from factors.alpha.base import FactorData
from factors.alpha.builtins.illiq import SizeProxy
from app_config.settings import get_settings

_cfg = get_settings().strategy

SIGNALS = Path("signals"); SIGNALS.mkdir(exist_ok=True)
LAST_REBAL = SIGNALS / "_last_rebalance.txt"
STATE_FILE = SIGNALS / "state.json"

# illiquidity v1.0 参数
TOP_N = _cfg.top_n
TIMING_MA = _cfg.timing_ma
REBAL_DAYS = _cfg.rebalance_days
LEVERAGE = _cfg.leverage
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
    print(f"  每日运行  {datetime.now(CHINA_TZ).strftime('%Y-%m-%d %H:%M')} CST  —  illiquidity v1.0")
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
    # SizeProxy: -ln(avg_amount_60d), zscore, MAD clip, shift(1) 防未来函数
    data = FactorData(close=close, volume=volume, amount=amount)
    factor_expr = SizeProxy(window=60).mad_clip(5).zscore().shift(1)
    factor = factor_expr.compute(data)

    # PureTrend MA16 timing (shared with v2.0, proven)
    timing_raw, small_nav, timing_dist = small_cap_timing(close, amount, TIMING_MA)
    dist = float(timing_dist.loc[last]) if last in timing_dist.index else 0.0
    base_in_market = bool(timing_raw.loc[last])

    # Band timing (LIVE 主决策 since 2026-06-07): dynamic exposure 0~1.5 driven by dist
    # exposure = clip(1 + dist*8, 0, 1.5) × I(dist > 0)
    # Band 用 leverage = exposure (dynamic), 取代 Binary 的固定 leverage 1.25
    # 已验证: Calmar 2.14 → 2.42 (+13%), Sharpe 1.89 → 1.86 (微降但 mdd 改善 1.9pp)
    _dc = max(min(dist, 0.5), -0.5)
    _raw = max(0.0, min(1.5, 1.0 + _dc * 8.0))
    band_exposure = float(_raw if _dc > 0 else 0.0)
    band_in_market = band_exposure > 0

    # LIVE 决策 = Band timing (主), Binary 保留作 SHADOW 对比
    binary_in_market = bool(base_in_market)   # SHADOW (旧 LIVE)
    in_market = bool(band_in_market)          # 新 LIVE 主决策 = Band

    # Regime 检测: dist.shift(1) > 0 → bull, ≤ 0 → bear
    # (T日只用T-1日dist, 防未来函数)
    regime_dist = float(timing_dist.shift(1).loc[last]) if last in timing_dist.index else 0.0
    regime = "bull" if regime_dist > 0 else "bear"

    print(f"  小盘指数 vs MA{TIMING_MA}: {dist:+.2%}")
    print(f"  Regime (shifted):         {'🟢 BULL' if regime == 'bull' else '🔴 BEAR'}")
    print(f"  Binary timing (SHADOW):    {'🟢持仓' if binary_in_market else '🔴空仓'}")
    print(f"  Band timing   (LIVE 主决策): exposure={band_exposure:.2f}x → "
          f"{'🟢持仓' if in_market else '🔴空仓观望'}")

    # 轮动信号
    if regime == "bear":
        print(f"  ⚠️ BEAR regime → 建议: 空仓资金配置 511010 国债ETF")
    else:
        print(f"  ℹ️ BULL regime → 全仓 illiq 股票")

    # ④ 持仓清单
    print("\n[4/6] 持仓清单...")
    f = factor.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(TOP_N).index.tolist()

    # ⑤ 调仓判断
    print("\n[5/6] 调仓判断...")
    state = load_state()
    is_rebal, reason, action = decide_action(close.index, last, in_market, state)
    print(f"  {'🔄 今日执行' if is_rebal else '⏸ 不执行'} — {reason}")

    # ⑥ 保存 signals
    print("\n[6/6] 保存信号...")
    # effective leverage = band_exposure (动态), 空仓时 0
    effective_leverage = round(band_exposure, 4) if in_market else 0.0
    signal = {
        "date": str(last.date()),
        "timing": "持仓" if in_market else "空仓",
        # ── LIVE 决策字段 (主) ──
        "in_market": in_market,                            # = band_in_market
        "band_exposure": round(band_exposure, 4),          # dynamic leverage 0~1.5
        "band_in_market": band_in_market,
        "timing_mode_live": "band",                        # 标识主决策来源
        "leverage": effective_leverage,                    # effective leverage = band_exposure
        # ── Regime + 轮动 (2026-06-08) ──
        "regime": regime,                                  # "bull" | "bear"
        "regime_dist": round(float(regime_dist), 4),       # shifted dist (防未来函数)
        "rotation": {
            "current_regime": regime,
            "recommend_stocks": regime == "bull",           # bull→全仓 illiq
            "recommend_bond": regime == "bear",             # bear→换债券(511010)
            "bond_code": "511010",
            "bond_name": "国债ETF",
            "bond_allocation": "全部闲置资金",               # bear=100%现金→债券
            "note": "BEAR时全部现金买511010; BULL时卖光511010买回股票",
        },
        # ── SHADOW: Binary timing (2026-06-07 Band 接替后保留对比) ──
        "binary_in_market_shadow": binary_in_market,
        "base_in_market": base_in_market,                  # binary 原始
        # ── 现有诊断字段 ──
        "small_index_vs_ma16": round(float(dist), 4),
        "is_execution_day": is_rebal,
        "is_rebalance_day": bool(is_rebal and in_market),
        "rebalance_reason": reason,
        "action": action,
        "holdings": holdings if in_market else [],
        "top_n": TOP_N,
        "strategy": "illiquidity", "strategy_version": "v1.0",
        # ── 向后兼容: 旧 shadow_band_* 字段保留 ──
        "shadow_band_exposure": round(band_exposure, 4),
        "shadow_band_in_market": band_in_market,
        "shadow_band_holdings": holdings if band_in_market else [],
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
    print(f"  Regime    : {'🟢 BULL' if regime == 'bull' else '🔴 BEAR'} (shifted)")
    print(f"  择时      : {signal['timing']}  (小盘指数{dist:+.2%} vs MA{TIMING_MA})")
    print(f"  执行      : {'是' if is_rebal else '否'} — {reason}")
    print(f"  操作      : {signal['action']}")
    if in_market:
        print(f"  持仓({len(holdings)}只): {', '.join(holdings[:12])}{' ...' if len(holdings)>12 else ''}")
    if regime == "bear":
        print(f"  💡 建议   : 空仓资金配置 511010 国债ETF")
    print(f"  已保存    : {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
