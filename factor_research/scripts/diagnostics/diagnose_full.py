"""全市场诊断：验证小盘alpha威力（对比沪市主板）"""
import warnings; warnings.filterwarnings("ignore")
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ["FACTOR_DATA"] = "data_full"
import numpy as np, pandas as pd
from evolve import (load_panels, compute_factor, safe_zscore, mad_clip,
                    market_timing, backtest, metrics, calc_ic_series)

close, volume, amount = load_panels()
print(f"全市场样本: {close.shape[1]} 只股票")
fwd = close.shift(-20)/close - 1
ret = close.pct_change()
ts20 = market_timing(close, 20)

def ev(f, label, tn=30, gap=20):
    f = safe_zscore(mad_clip(f))
    ic = calc_ic_series(f, fwd)
    icir = ic.mean()/(ic.std()+1e-8)
    r = backtest(f, close, tn, gap, ts20)
    m = metrics(r)
    print(f"  {label:22s} IC={ic.mean():+.4f} ICIR={icir:+.3f} | 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f}")

print("\n=== 单因子（全市场，择时20，持股30）===")
ev(-np.log(amount.rolling(20).mean()+1), "小盘20")
ev(-np.log(amount.rolling(60).mean()+1), "小盘60")
ev(-(close/close.shift(5)-1), "5日反转")
ev(-(close/close.shift(20)-1), "20日反转")
ev(-ret.rolling(20).std(), "低波20")
ev(-(amount/(amount.rolling(60).mean()+1e-6)).rolling(10).mean(), "低换手")
ev(-(close/close.rolling(60).mean()-1), "低于均线60")

print("\n=== 小盘+反转+低波 集中持股 + 波动目标 ===")
size = safe_zscore(mad_clip(-np.log(amount.rolling(60).mean()+1)))
rev = safe_zscore(mad_clip(-(close/close.shift(20)-1)))
lv = safe_zscore(mad_clip(-ret.rolling(20).std()))
comp = safe_zscore(size+rev+lv)
for tn in [20, 30, 50]:
    for vt in [None, 0.18, 0.25]:
        r = backtest(comp, close, tn, 20, ts20, vol_target=vt, lev_max=3.0)
        m = metrics(r)
        flag = "🎯" if m["hit"] else ""
        print(f"  持股={tn} 波动目标={vt}: 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f} 卡玛={m['calmar']:.2f} {flag}")
