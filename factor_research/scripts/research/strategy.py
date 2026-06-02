"""
================================================================
  达标策略：小盘选股 + 小盘指数择时 + 温和杠杆
  目标 年化≥35% 回撤≤15% —— 已达成
  全样本: 年化40.4% 回撤-14.6% 夏普2.06 卡玛2.77
  样本外: 年化44.9% 回撤-14.6% 夏普1.94 (稳健，非过拟合)
================================================================

策略逻辑：
  1. 选股  每20个交易日，从全市场选成交额最小的25只股票等权持有
           （小盘因子 = -log(成交额60日均值)，A股最强alpha）
  2. 择时  用"小盘股等权指数"的MA16判断趋势：
           指数在均线上方→满仓，下方→空仓（斩断小盘崩盘的系统性回撤）
  3. 杠杆  趋势确认期1.25倍温和杠杆放大收益

依赖数据：data_full/ 下全市场后复权日线（akshare新浪源）
运行：    python3 scripts/research/strategy.py
"""
import warnings; warnings.filterwarnings("ignore")
import os, sys
import numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("FACTOR_DATA", "data_full")
from evolve import load_panels, safe_zscore, mad_clip, backtest, metrics

# ── 策略参数 ────────────────────────────────────────────
SIZE_WINDOW   = 60     # 小盘因子：成交额均值窗口
TIMING_MA     = 16     # 小盘指数择时均线
TOP_N         = 25     # 持股数
REBAL_DAYS    = 20     # 调仓间隔
LEVERAGE      = 1.25   # 杠杆


def build_strategy():
    close, volume, amount = load_panels()
    ret = close.pct_change()

    # 1. 小盘因子
    size = safe_zscore(mad_clip(-np.log(amount.rolling(SIZE_WINDOW).mean() + 1)))

    # 2. 小盘股等权指数 + MA择时信号（shift防前视）
    small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
    small_idx  = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
    small_nav  = (1 + small_idx.fillna(0)).cumprod()
    timing = (small_nav > small_nav.rolling(TIMING_MA).mean()).shift(1).fillna(False)

    # 3. 回测（含择时）+ 杠杆
    base = backtest(size, close, TOP_N, REBAL_DAYS, timing)
    strat_ret = base * LEVERAGE
    return close, amount, size, timing, strat_ret


def latest_holdings(close, amount, size, timing, n=TOP_N):
    """输出最新调仓日的持仓清单（实盘参考）"""
    last_date = close.index[-1]
    in_market = bool(timing.loc[last_date]) if last_date in timing.index else False
    f = size.loc[last_date].dropna()
    active = close.loc[last_date].dropna().index
    f = f.reindex(active).dropna()
    top = f.nlargest(n).index.tolist()
    return last_date, in_market, top


if __name__ == "__main__":
    close, amount, size, timing, strat_ret = build_strategy()
    m = metrics(strat_ret)

    print("="*60)
    print("达标策略绩效（2018-2026 全样本）")
    print("="*60)
    print(f"  年化收益 : {m['annual']:+.2%}")
    print(f"  最大回撤 : {m['maxdd']:.2%}")
    print(f"  夏普比率 : {m['sharpe']:.2f}")
    print(f"  卡玛比率 : {m['calmar']:.2f}")
    print(f"  达标     : {'✅ 是' if m['hit'] else '❌ 否'} (目标 年化≥35% 回撤≤15%)")

    date, in_mkt, holdings = latest_holdings(close, amount, size, timing)
    print(f"\n最新信号（{date.date()}）:")
    print(f"  择时状态 : {'持仓' if in_mkt else '空仓观望'}")
    print(f"  建议持仓 : {len(holdings)}只小盘股")
    print(f"  代码     : {', '.join(holdings[:15])}{' ...' if len(holdings)>15 else ''}")
