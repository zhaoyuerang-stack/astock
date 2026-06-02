"""交易成本敏感性 —— v2.0策略在不同换手成本+杠杆融资下的真实年化"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from lake.load_lake import load_prices
from evolve import safe_zscore, mad_clip, backtest, metrics

px = load_prices(start="2018-01-01")   # 与v2.0同区间
close, amount = px["close"], px["amount"]
ret = close.pct_change()
size = safe_zscore(mad_clip(-np.log(amount.rolling(60).mean() + 1)))
small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
small_nav = (1 + small_idx.fillna(0)).cumprod()
timing = (small_nav > small_nav.rolling(16).mean()).shift(1).fillna(False)

FIN_COST_Y = 0.25 * 0.065        # 1.25x杠杆的年融资成本≈1.6%
fin_daily = FIN_COST_Y / 252

print("v2.0 (2018-2026) 交易成本敏感性\n")
print(f"{'单次换手成本':<14}{'年化':>9}{'回撤':>9}{'夏普':>7}{'达标':>5}  说明")
print("-" * 70)
for cost, desc in [(0.0015, "回测原值(单边·偏乐观)"),
                   (0.003,  "双边·大盘股口径"),
                   (0.005,  "双边+小盘冲击(中性)"),
                   (0.007,  "双边+小盘冲击(保守)"),
                   (0.010,  "极端小盘冲击")]:
    base = backtest(size, close, 25, 20, timing, cost=cost)
    strat = base * 1.25 - fin_daily * (timing.reindex(base.index).fillna(False))  # 持仓日扣融资
    m = metrics(strat)
    print(f"{cost:>6.2%}        {m['annual']:>8.1%}{m['maxdd']:>9.1%}{m['sharpe']:>7.2f}"
          f"{'✅' if m['hit'] else '❌':>5}  {desc}")

print("\n注: 已含1.25x杠杆的融资成本(~1.6%/年,仅持仓日扣)")
