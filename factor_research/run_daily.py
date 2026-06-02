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
import numpy as np, pandas as pd
from lake.load_lake import load_prices
from lake.validator import DataValidator
from evolve import safe_zscore, mad_clip

SIGNALS = Path("signals"); SIGNALS.mkdir(exist_ok=True)
LAST_REBAL = SIGNALS / "_last_rebalance.txt"

# 策略参数（与 v2.0 一致）
TOP_N, SIZE_WIN, TIMING_MA, REBAL_DAYS, LEVERAGE = 25, 60, 16, 20, 1.25


def need_rebalance(trade_dates, last_date):
    """距上次调仓 ≥ REBAL_DAYS 个交易日 → 今天调仓"""
    if not LAST_REBAL.exists():
        return True, "首次调仓"
    last_rebal = pd.Timestamp(LAST_REBAL.read_text().strip())
    gap = int(((trade_dates > last_rebal) & (trade_dates <= last_date)).sum())
    if gap >= REBAL_DAYS:
        return True, f"距上次调仓 {gap} 交易日 (≥{REBAL_DAYS})"
    return False, f"距上次调仓 {gap} 交易日 (<{REBAL_DAYS})，维持原仓位"


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
    px = load_prices(start="2010-01-01")
    close, amount = px["close"], px["amount"]
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
    ret = close.pct_change()
    size = safe_zscore(mad_clip(-np.log(amount.rolling(SIZE_WIN).mean() + 1)))
    small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
    small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
    small_nav = (1 + small_idx.fillna(0)).cumprod()
    ma = small_nav.rolling(TIMING_MA).mean()
    in_market = bool(small_nav.iloc[-1] > ma.iloc[-1])
    dist = small_nav.iloc[-1] / ma.iloc[-1] - 1
    print(f"  小盘指数 vs MA{TIMING_MA}: {dist:+.2%} → {'🟢持仓' if in_market else '🔴空仓观望'}")

    # ④ 持仓清单
    print("\n[4/6] 持仓清单...")
    f = size.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(TOP_N).index.tolist()

    # ⑤ 调仓判断
    print("\n[5/6] 调仓判断...")
    is_rebal, reason = need_rebalance(close.index, last)
    print(f"  {'🔄 今日调仓' if is_rebal else '⏸ 不调仓'} — {reason}")

    # ⑥ 保存 signals
    print("\n[6/6] 保存信号...")
    signal = {
        "date": str(last.date()),
        "timing": "持仓" if in_market else "空仓",
        "in_market": in_market,
        "small_index_vs_ma16": round(float(dist), 4),
        "is_rebalance_day": is_rebal,
        "rebalance_reason": reason,
        "action": ("调仓买入" if (is_rebal and in_market) else
                   "清仓" if not in_market else "维持原仓位"),
        "holdings": holdings if in_market else [],
        "top_n": TOP_N, "leverage": LEVERAGE,
        "strategy_version": "v2.0",
    }
    out = SIGNALS / f"{last.date()}.json"
    out.write_text(json.dumps(signal, ensure_ascii=False, indent=2))
    if is_rebal:
        LAST_REBAL.write_text(str(last.date()))   # 调仓日才更新基准

    # ── 终端总结 ──
    print("\n" + "=" * 60)
    print(f"  日期      : {last.date()}")
    print(f"  择时      : {signal['timing']}  (小盘指数{dist:+.2%} vs MA16)")
    print(f"  调仓      : {'是' if is_rebal else '否'} — {reason}")
    print(f"  操作      : {signal['action']}")
    if in_market:
        print(f"  持仓({len(holdings)}只): {', '.join(holdings[:12])}{' ...' if len(holdings)>12 else ''}")
    print(f"  已保存    : {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
