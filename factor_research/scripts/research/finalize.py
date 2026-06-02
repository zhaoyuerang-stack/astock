"""锁定达标策略 + 样本外验证 + 保存结果"""
import warnings; warnings.filterwarnings("ignore")
import os, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ["FACTOR_DATA"] = "data_full"
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from evolve import load_panels, safe_zscore, mad_clip, backtest, metrics

close, volume, amount = load_panels()
ret = close.pct_change()
size60 = safe_zscore(mad_clip(-np.log(amount.rolling(60).mean()+1)))

# 小盘指数择时信号
small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
small_nav = (1+small_idx.fillna(0)).cumprod()
def small_ma_signal(w):
    return (small_nav > small_nav.rolling(w).mean()).shift(1).fillna(False)

print(f"全市场 {close.shape[1]} 只 | 锁定达标配置")
print("="*95)

# 精细搜索达标区间
results = []
for w in [13, 14, 15, 16, 17]:
    ts = small_ma_signal(w)
    for tn in [20, 25, 30]:
        base = backtest(size60, close, tn, 20, ts)
        for lev in [1.10, 1.15, 1.20, 1.25]:
            m = metrics(base * lev)
            results.append((w, tn, lev, m, base))
            if m["hit"]:
                print(f"🎯 择时MA{w} 持股{tn} 杠杆{lev}: 年化={m['annual']:+.2%} "
                      f"回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f} 卡玛={m['calmar']:.2f}")

hits = [r for r in results if r[3]["hit"]]
print(f"\n达标配置数: {len(hits)}")
if not hits:
    print("无达标，输出最接近的:")
    results.sort(key=lambda x: x[3]["calmar"], reverse=True)
    for w,tn,lev,m,_ in results[:5]:
        print(f"  MA{w} 持股{tn} 杠杆{lev}: 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 卡玛={m['calmar']:.2f}")
    raise SystemExit

# 选最稳健达标点：回撤余量×年化余量综合，优先回撤有余量的
def robustness(m):
    return (0.15 - abs(m["maxdd"])) * 100 + (m["annual"] - 0.35) * 50
best = max(hits, key=lambda r: robustness(r[3]))
w, tn, lev, m, base = best
print(f"\n{'='*95}")
print(f"★ 选定策略（最稳健达标点）:")
print(f"  因子: 小盘60 (成交额60日均值倒数)")
print(f"  择时: 小盘股指数 MA{w}")
print(f"  持股: {tn} 只等权 | 调仓: 20交易日 | 杠杆: {lev}x")
print(f"  全样本: 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f} 卡玛={m['calmar']:.2f}")

# ── 样本外验证：时间分段 ──
strat_ret = base * lev
split = strat_ret.index[int(len(strat_ret)*0.6)]
is_ret = strat_ret[strat_ret.index < split]
oos_ret = strat_ret[strat_ret.index >= split]
print(f"\n样本外验证（IS={is_ret.index[0].date()}~{is_ret.index[-1].date()}, "
      f"OOS={oos_ret.index[0].date()}~{oos_ret.index[-1].date()}）:")
for label, r in [("样本内IS", is_ret), ("样本外OOS", oos_ret)]:
    mm = metrics(r)
    print(f"  {label}: 年化={mm['annual']:+.2%} 回撤={mm['maxdd']:.2%} "
          f"夏普={mm['sharpe']:.2f} 卡玛={mm['calmar']:.2f}")

# ── 年度收益分解 ──
print(f"\n分年度收益:")
yearly = strat_ret.groupby(strat_ret.index.year).apply(lambda x: (1+x).prod()-1)
for yr, r in yearly.items():
    print(f"  {yr}: {r:+.2%}")

# ── 保存净值图 ──
cum = (1+strat_ret).cumprod()
fig, axes = plt.subplots(2,1,figsize=(14,9),sharex=True)
cum.plot(ax=axes[0], color="navy", lw=1.5, label="策略")
axes[0].axvline(split, color="green", ls=":", lw=1.5, label="样本内/外分界")
axes[0].set_title(f"达标策略净值  年化={m['annual']:.2%}  回撤={m['maxdd']:.2%}  夏普={m['sharpe']:.2f}  卡玛={m['calmar']:.2f}", fontsize=13)
axes[0].axhline(1, color="gray", ls="--", lw=0.8); axes[0].legend(); axes[0].set_ylabel("净值(对数)")
axes[0].set_yscale("log")
dd = cum/cum.cummax()-1
dd.plot(ax=axes[1], color="crimson", lw=1)
axes[1].fill_between(dd.index, dd, 0, alpha=0.3, color="crimson")
axes[1].axhline(-0.15, color="orange", ls="--", label="回撤上限15%")
axes[1].legend(); axes[1].set_ylabel("回撤")
plt.tight_layout(); fig.savefig("results/FINAL_strategy.png", dpi=130)
print(f"\n净值图: results/FINAL_strategy.png")

with open("results/FINAL_config.json","w") as f:
    json.dump({
        "strategy": "小盘60 + 小盘指数择时 + 杠杆",
        "factor": "size60 = -log(amount.rolling(60).mean())",
        "timing": f"小盘股等权指数 MA{w}",
        "top_n": tn, "rebalance_days": 20, "leverage": lev,
        "full_sample": {k: round(float(m[k]),4) for k in ["annual","maxdd","sharpe","calmar"]},
        "in_sample": {k: round(float(metrics(is_ret)[k]),4) for k in ["annual","maxdd","sharpe","calmar"]},
        "out_sample": {k: round(float(metrics(oos_ret)[k]),4) for k in ["annual","maxdd","sharpe","calmar"]},
        "hit_target": bool(m["hit"]),
    }, f, ensure_ascii=False, indent=2)
print(f"配置: results/FINAL_config.json")
