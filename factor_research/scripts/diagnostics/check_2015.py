"""核查 v2.1 的 2015+389% —— 真实小盘疯牛 vs 数据异常拉高"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from lake.load_lake import load_prices
from evolve import safe_zscore, mad_clip, backtest

px = load_prices(start="2010-01-01")
close, amount = px["close"], px["amount"]
ret = close.pct_change()
size = safe_zscore(mad_clip(-np.log(amount.rolling(60).mean() + 1)))
small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
small_nav = (1 + small_idx.fillna(0)).cumprod()
timing = (small_nav > small_nav.rolling(16).mean()).shift(1).fillna(False)
base = backtest(size, close, 25, 20, timing)
strat = base * 1.25

s15 = strat[strat.index.year == 2015]
print(f"=== v2.1 策略 2015 全年: {(1+s15).prod()-1:+.0%} ({len(s15)}交易日) ===\n")

# ① 月度收益
print("① 月度收益:")
monthly = s15.groupby(s15.index.month).apply(lambda x: (1+x).prod()-1)
print("  " + " ".join(f"{m}月:{r:+.0%}" for m, r in monthly.items()))

# ② 极端单日(>15% = 数据异常信号，A股涨停板单日上限远低于此)
print("\n② 极端单日(策略日收益>15%，杠杆1.25下对应底层>12%):")
ext = s15[s15.abs() > 0.15]
print(f"  {len(ext)}个: " + (" ".join(f"{d.date()}:{r:+.0%}" for d, r in ext.items()) if len(ext) else "无"))

# ③ 对比小盘指数2015真实涨幅(创业板2015上半年+170%是历史事实)
si15 = small_idx[small_idx.index.year == 2015].fillna(0)
print(f"\n③ 小盘股等权指数2015: {(1+si15).prod()-1:+.0%} (对比创业板指上半年+170%)")
print(f"   小盘指数最大单日: {si15.max():+.1%}, 最小: {si15.min():+.1%}")

# ④ 抽查2015年中某持仓股的真实数据(看有无复权异常假涨)
print("\n④ 抽查2015-06持仓股(看数据是否正常):")
d = pd.Timestamp("2015-06-15")
avail = close.loc[:d].iloc[-1].dropna().index
f = size.loc[:d].iloc[-1].reindex(avail).dropna()
top5 = f.nlargest(5).index.tolist()
for c in top5[:5]:
    cp = close[c].loc["2015-01-01":"2015-06-30"].dropna()
    if len(cp) > 1:
        print(f"  {c}: 2015上半年 {cp.iloc[0]:.1f}→{cp.iloc[-1]:.1f} ({cp.iloc[-1]/cp.iloc[0]-1:+.0%})")
