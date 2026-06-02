"""诊断：理解收益天花板，定位突破口"""
import warnings; warnings.filterwarnings("ignore")
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from evolve import (load_panels, compute_factor, safe_zscore,
                    market_timing, backtest, metrics, SEARCH_SPACE, calc_ic_series)

close, volume, amount = load_panels()
fwd = close.shift(-20)/close - 1

# 构建最优组合的因子（来自进化结果）
best_factors = [
    ("turnover", {"n":5}), ("turnover", {"n":20}),
    ("price_ma", {"n":60}), ("low_vol", {"n":40}),
    ("price_ma", {"n":20}), ("momentum_quality", {"n":40}),
]
genes = []
for name, params in best_factors:
    f = compute_factor(name, params, close, volume, amount)
    ic = calc_ic_series(f, fwd)
    icir = ic.mean()/(ic.std()+1e-8)
    genes.append({"factor": f, "icir": icir})

total = sum(abs(g["icir"]) for g in genes)
comp = safe_zscore(sum(g["factor"]*(g["icir"]/total) for g in genes))

print("\n=== 诊断1: 择时 vs 不择时（持股20，调仓20d）===")
for tm in [None, 20, 40, 60]:
    ts = market_timing(close, tm) if tm else None
    ret = backtest(comp, close, 20, 20, ts)
    m = metrics(ret)
    # 持仓比例
    hold_pct = (ts.reindex(close.index).fillna(False).mean()*100) if ts is not None else 100
    print(f"  择时={str(tm):5s} 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f} 持仓占比={hold_pct:.0f}%")

print("\n=== 诊断2: 持股集中度（择时20，调仓20d）===")
ts20 = market_timing(close, 20)
for tn in [10, 15, 20, 30, 50]:
    ret = backtest(comp, close, tn, 20, ts20)
    m = metrics(ret)
    print(f"  持股={tn:3d} 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f} 卡玛={m['calmar']:.2f}")

print("\n=== 诊断3: 调仓频率（持股15，择时20）===")
for gap in [3, 5, 10, 20]:
    ret = backtest(comp, close, 15, gap, ts20)
    m = metrics(ret)
    print(f"  调仓={gap:2d}d 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f}")

print("\n=== 诊断4: 杠杆效应（持股15，调仓10，择时20）===")
ret_base = backtest(comp, close, 15, 10, ts20)
for lev in [1.0, 1.3, 1.5, 2.0]:
    ret_lev = ret_base * lev
    m = metrics(ret_lev)
    print(f"  杠杆={lev:.1f}x 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f}")

print("\n=== 诊断5: 纯反转因子集中持股（A股反转效应）===")
rev = compute_factor("reversal", {"n":5}, close, volume, amount)
for tn in [10, 15, 20]:
    for gap in [3, 5]:
        ret = backtest(rev, close, tn, gap, ts20)
        m = metrics(ret)
        print(f"  反转 持股={tn} 调仓={gap}d: 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f}")
