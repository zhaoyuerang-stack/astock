"""验证回测逻辑：单因子能否产出合理净值"""
import warnings; warnings.filterwarnings("ignore")
import os, sys
import numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from evolve import load_panels, compute_factor, safe_zscore

def backtest_v2(composite_factor, close, top_n=80, rebal_gap=10):
    daily_ret = close.pct_change()
    factor_dates = composite_factor.dropna(how="all").index.intersection(close.index)
    if len(factor_dates) < 60:
        return pd.Series(dtype=float)
    rebal_dates = list(factor_dates[::rebal_gap])
    weight_panel = {}
    for rd in rebal_dates:
        f = composite_factor.loc[rd].dropna()
        active = close.loc[rd].dropna().index
        f = f.reindex(active).dropna()
        if len(f) < top_n:
            continue
        top = f.nlargest(top_n).index
        weight_panel[rd] = pd.Series(1.0/top_n, index=top)
    if not weight_panel:
        return pd.Series(dtype=float)
    sorted_rebal = np.array(sorted(weight_panel.keys()))
    port_rets = {}
    for dt in close.index:
        idx = np.searchsorted(sorted_rebal, dt, side="left") - 1
        if idx < 0:
            continue
        cur_w = weight_panel[sorted_rebal[idx]]
        common = cur_w.index.intersection(daily_ret.columns)
        if len(common) == 0:
            continue
        r = (cur_w[common] * daily_ret.loc[dt, common].fillna(0)).sum()
        port_rets[dt] = r
    return pd.Series(port_rets).dropna()

def metrics(ret):
    annual = ret.mean()*252
    vol = ret.std()*np.sqrt(252)
    sharpe = annual/vol if vol>0 else 0
    cum = (1+ret).cumprod()
    maxdd = (cum/cum.cummax()-1).min()
    return annual, maxdd, sharpe, len(ret)

close, volume, amount = load_panels()

# 测几个Gen0里最强的因子
tests = [
    ("price_ma", {"n":60}),
    ("low_vol", {"n":10}),
    ("turnover", {"n":5}),
    ("mom", {"n":40,"skip":0}),
]
for name, params in tests:
    f = compute_factor(name, params, close, volume, amount)
    ret = backtest_v2(f, close, top_n=80, rebal_gap=10)
    if len(ret) > 0:
        a, dd, sh, n = metrics(ret)
        print(f"{name:12s}{str(params):20s} 年化={a:+.2%} 回撤={dd:.2%} 夏普={sh:.2f} 天数={n}")
    else:
        print(f"{name:12s}{str(params):20s} 回测为空!")
