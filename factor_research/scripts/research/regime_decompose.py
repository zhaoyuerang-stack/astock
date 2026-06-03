"""v2.0 回测诊断:净值/回撤/滚动波动率图 + 收益按年分解(含年化波动率)。

用法(cwd=factor_research): /usr/bin/python3 -m scripts.research.regime_decompose
输出: reports/v2_diagnostics.png + 控制台分解表
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np                                          # noqa: E402
import matplotlib                                           # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                             # noqa: E402

from core.backtest import metrics, yearly_returns          # noqa: E402
from factory.evaluator import prepare_context              # noqa: E402

close, amount, library, ret = prepare_context("2010-01-01")

print("=== v2.0 年度收益 ===")
for y, r in yearly_returns(ret).items():
    print(f"  {int(y)}: {r:+7.1%}" + ("   <- 极端" if abs(r) > 0.5 else ""))


def seg(r, label):
    m = metrics(r)
    vol = float(r.std() * np.sqrt(252))
    print(f"  {label:<22} 年化{m['annual']:+6.1%} 波动{vol:5.1%} 回撤{m['maxdd']:+6.1%} "
          f"夏普{m['sharpe']:5.2f} 卡玛{m.get('calmar', 0):5.2f}")


print("\n=== 三段 × 剔除极端年(剔除后回撤/波动因净值不连续仅供参考)===")
for label, y0 in [("样本内2018-2026", 2018), ("压力2010-2026", 2010)]:
    r = ret[ret.index.year >= y0]
    print(f"\n[{label}]")
    seg(r, "全样本")
    seg(r[r.index.year != 2025], "剔除2025")
    seg(r[~r.index.year.isin([2025, 2015, 2014])], "剔除2025+2014/15")

# ── 回测诊断图:净值(log) / 回撤 / 滚动波动率 ──
nav = (1 + ret).cumprod()
dd = nav / nav.cummax() - 1
roll_vol = ret.rolling(60).std() * np.sqrt(252)

fig, ax = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
ax[0].plot(nav.index, nav.values, lw=1.0)
ax[0].set_yscale("log")
ax[0].set_title("v2.0 small-cap-size  NAV (log scale)  2010-2026")
ax[0].grid(alpha=0.3)
ax[1].fill_between(dd.index, dd.values, 0, color="crimson", alpha=0.4)
ax[1].set_title("Drawdown")
ax[1].grid(alpha=0.3)
ax[2].plot(roll_vol.index, roll_vol.values, color="purple", lw=1.0)
ax[2].axhline(float(roll_vol.mean()), color="gray", ls="--", lw=0.8,
              label=f"mean {float(roll_vol.mean()):.0%}")
ax[2].set_title("Rolling 60d annualized volatility")
ax[2].legend(loc="upper right")
ax[2].grid(alpha=0.3)
plt.tight_layout()
Path("reports").mkdir(exist_ok=True)
plt.savefig("reports/v2_diagnostics.png", dpi=90)
print("\n图已保存: reports/v2_diagnostics.png")
