"""
策略迁移到 data_lake 加载层复测 —— 打假验证
不再依赖 FACTOR_DATA=data_full 和 evolve.load_panels()(有active过滤=幸存者偏差)，
改用 lake.load_lake.load_prices(无过滤，更真实)。

验证：①2018-2026对比旧40.4%(看active过滤/幸存者偏差的影响)
      ②2010-2026压力测试(含2015股灾/2017小盘崩盘)
"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
os.chdir(Path(__file__).parent)
import numpy as np, pandas as pd
from lake.load_lake import load_prices
from evolve import safe_zscore, mad_clip, backtest, metrics


def build_strategy_lake(start):
    px = load_prices(start=start)            # data_lake，无active过滤(无幸存者偏差)
    close, amount = px["close"], px["amount"]
    print(f"  载入 {close.shape[1]}只 × {close.shape[0]}日 [{close.index[0].date()}~{close.index[-1].date()}]", flush=True)
    ret = close.pct_change()
    # 小盘60因子（与strategy.py完全一致）
    size = safe_zscore(mad_clip(-np.log(amount.rolling(60).mean() + 1)))
    # 小盘指数MA16择时
    small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
    small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
    small_nav = (1 + small_idx.fillna(0)).cumprod()
    timing = (small_nav > small_nav.rolling(16).mean()).shift(1).fillna(False)
    base = backtest(size, close, 25, 20, timing)
    return base * 1.25


for label, start in [("① 2018-2026 (对比旧 年化40.4%)", "2018-01-01"),
                     ("② 2010-2026 (压力测试·含2015股灾/2017小盘崩盘)", "2010-01-01")]:
    print(f"\n{label}", flush=True)
    strat = build_strategy_lake(start)
    m = metrics(strat)
    print(f"  → 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f} "
          f"卡玛={m['calmar']:.2f} 达标={'✅' if m['hit'] else '❌'}", flush=True)
    yearly = strat.groupby(strat.index.year).apply(lambda x: (1 + x).prod() - 1)
    print("  分年度:", " ".join(f"{y}:{r:+.0%}" for y, r in yearly.items()), flush=True)
