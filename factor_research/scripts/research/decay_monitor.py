"""illiquidity v1.0 失效监控: 3 个定量信号 + 状态判定。
① illiquidity 因子滚动 RankIC (转负 = 非流动性溢价失效)
② 小盘相对全市场动量 (PureTrend 择时的命门)
③ illiquidity 策略滚动 12 月夏普
两项同时触发 → 预警/复审退役。

用法(cwd=factor_research): /usr/bin/python3 scripts/research/decay_monitor.py
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel
from strategies.small_cap import load_price_panels
from factors.utils import safe_zscore, mad_clip
from factors.small_cap import small_cap_timing

# ── illiquidity factor ──
class Illiq:
    def __init__(self, w=20): self.w = w
    def __call__(self, c, v, a, d):
        r = c.pct_change(fill_method=None).abs().replace([np.inf, -np.inf], np.nan)
        return safe_zscore(mad_clip((r/(a+1)).rolling(self.w).mean()))

# ── Load data ──
close, volume, amount = load_price_panels("2010-01-01")
td = close.index
factor = Illiq(20)(close, volume, amount, td)

# ① illiquidity 因子滚动 RankIC (vs 未来 20 日收益; 转负 = 非流动性溢价失效)
fwd = close.pct_change(20, fill_method=None).shift(-20)
ic = {}
for t in factor.index[::20]:
    f = factor.loc[t].dropna()
    if t not in fwd.index: continue
    r = fwd.loc[t].reindex(f.index).dropna()
    common = f.index.intersection(r.index)
    if len(common) >= 50:
        ic[t] = f[common].rank().corr(r[common].rank())
ic = pd.Series(ic)
roll_ic = ic.rolling(12).mean()

# ② 小盘相对全市场动量 (PureTrend 择时命门; <0 = 小盘逆风)
dret = close.pct_change(fill_method=None)
mkt = dret.mean(axis=1)
small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
small = (dret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
rel = (1 + small.fillna(0)).cumprod() / (1 + mkt.fillna(0)).cumprod()
rel_mom = rel / rel.rolling(120).mean() - 1

# ③ illiquidity 策略滚动 12 月夏普
def build_weights(factor, close, n=25, reb=20):
    fdates = factor.dropna(how="all").index.intersection(close.index)
    if len(fdates) < 50: return {}
    w = {}
    for rd in list(fdates[::reb]):
        pos = close.index.get_loc(rd)
        if pos+1 >= len(close.index): continue
        eff = close.index[pos+1]
        f = factor.loc[rd].dropna()
        act = close.loc[rd].dropna().index
        f = f.reindex(act).dropna()
        if len(f) < n: continue
        w[eff] = pd.Series(1.0/n, index=f.nlargest(n).index)
    return w

pt, _, _ = small_cap_timing(close, amount, 16)
w = build_weights(factor, close)
prices = PricePanel(close=close, volume=volume, amount=amount)
r = BacktestEngine(prices=prices, config=BacktestConfig(start="2010-01-01", leverage=1.25)).run(
    Signal(weights=w, timing=pt.astype(float)))
ret = r.returns
roll_sharpe = ret.rolling(252).mean() / ret.rolling(252).std() * np.sqrt(252)

# ── Status assessment ──
cur_ic = float(roll_ic.dropna().iloc[-1])
cur_rel = float(rel_mom.dropna().iloc[-1])
cur_sh = float(roll_sharpe.dropna().iloc[-1])

print("=== illiquidity v1.0 失效监控 ===")
print(f"  ① illiquidity因子 滚动12 RankIC: {cur_ic:+.3f}  (历史均 {ic.mean():+.3f}; <0 = 溢价失效)")
print(f"  ② 小盘相对动量(6月)           : {cur_rel:+.1%}  (<0 = 小盘逆风)")
print(f"  ③ illiquidity 滚动12月夏普    : {cur_sh:.2f}  (历史均 {roll_sharpe.mean():.2f})")

ic_peak = float(roll_ic.dropna().iloc[-12:].max())
grades, msgs = [], []
if cur_ic < 0:
    grades.append(2); msgs.append("非流动性IC转负(已失效)")
elif cur_ic < ic.mean() * 0.4 or (ic_peak > 0 and cur_ic / ic_peak - 1 < -0.5):
    grades.append(1); msgs.append("非流动性IC见顶下行")
else:
    grades.append(0)
if cur_rel < -0.05:
    grades.append(2); msgs.append("小盘逆风")
elif cur_rel < 0:
    grades.append(1); msgs.append("小盘走弱")
else:
    grades.append(0)
if cur_sh < 0.5:
    grades.append(2); msgs.append("滚动夏普<0.5")
elif cur_sh < roll_sharpe.mean() * 0.6:
    grades.append(1); msgs.append("夏普回落")
else:
    grades.append(0)

n_warn, n_watch = grades.count(2), grades.count(1)
if n_warn >= 1 or n_watch >= 2:
    status = "🔴 预警(减仓/复审退役)"
elif n_watch == 1:
    status = "🟡 观察"
else:
    status = "🟢 健康"

print(f"\n  当前状态: {status}" + (f"  触发: {', '.join(msgs)}" if msgs else ""))
print("  前瞻阈值: IC<历史均×0.4 或从近12月峰值回落>50%=观察(转负=预警); "
      "小盘动量<0=观察(<-5%=预警); 夏普<历史均×0.6=观察(<0.5=预警)。任一预警或≥2观察→🔴")

Path("reports").mkdir(exist_ok=True)
Path("reports/decay_status.json").write_text(json.dumps({
    "strategy": "illiquidity v1.0",
    "status": status, "ic": round(cur_ic, 4), "ic_hist": round(float(ic.mean()), 4),
    "rel_mom": round(cur_rel, 4), "roll_sharpe": round(cur_sh, 2),
    "msgs": msgs, "updated": str(roll_ic.dropna().index[-1].date()),
}, ensure_ascii=False, indent=2))
print("  → 状态已写 reports/decay_status.json")

# ── Plot ──
fig, ax = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
ax[0].plot(roll_ic.index, roll_ic.values)
ax[0].axhline(0, color="r", ls="--", lw=.8)
ax[0].set_title("(1) illiquidity factor rolling-12 RankIC  (<0 = premium gone)")
ax[0].grid(alpha=.3)
ax[1].plot(rel_mom.index, rel_mom.values, color="green")
ax[1].axhline(-0.05, color="r", ls="--", lw=.8)
ax[1].set_title("(2) small-cap relative momentum 6m  (<-5% = headwind)")
ax[1].grid(alpha=.3)
ax[2].plot(roll_sharpe.index, roll_sharpe.values, color="purple")
ax[2].axhline(0.5, color="r", ls="--", lw=.8)
ax[2].set_title("(3) illiquidity v1.0 rolling-12m Sharpe  (<0.5 = weak)")
ax[2].grid(alpha=.3)
plt.tight_layout()
plt.savefig("reports/illiq_decay_monitor.png", dpi=90)
print("图: reports/illiq_decay_monitor.png")
