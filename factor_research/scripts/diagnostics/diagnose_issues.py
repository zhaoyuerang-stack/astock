"""诊断133只真问题的具体异常点，判断性质与修复方法"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import pandas as pd
from lake.validator import DataValidator

cal = pd.read_parquet("data_lake/meta/trade_calendar.parquet")["date"]
v = DataValidator(calendar=cal)

ohlc, zombie, jump = [], [], []
for fp in sorted(Path("data_lake/price/daily").glob("*.parquet")):
    df = pd.read_parquet(fp)
    r = v.validate(fp.stem, df)
    if r["ok"]:
        continue
    for iss in r["issues"]:
        if "OHLC" in iss:
            ohlc.append((fp.stem, df))
        elif "僵尸" in iss:
            zombie.append((fp.stem, df))
        elif "跳变" in iss:
            jump.append((fp.stem, df))

print(f"问题统计: OHLC错误{len(ohlc)}只 僵尸{len(zombie)}只 跳变{len(jump)}只\n")

print("=== OHLC逻辑错误 样本(看具体异常行) ===")
for code, df in ohlc[:3]:
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    bad = df[(l > o) | (l > c) | (h < o) | (h < c) | (df[["open","high","low","close"]] < 0).any(axis=1)]
    print(f"[{code}] {len(bad)}个异常点:")
    print(bad[["date","open","high","low","close","volume"]].head(2).to_string(index=False))

print("\n=== 价格跳变>50% 样本(看是除权还是错误) ===")
for code, df in jump[:3]:
    ret = df["close"].pct_change()
    big = df[ret.abs() > 0.5]
    print(f"[{code}] {len(big)}处跳变, 首处:")
    idx = big.index[0]
    print(df.loc[max(0,idx-1):idx+1, ["date","close","volume"]].to_string(index=False))

print("\n=== 僵尸值 样本(看是停牌复牌还是错误) ===")
for code, df in zombie[:3]:
    same = (df["close"].diff() == 0)
    run = same.rolling(5).sum()
    idx = run[run >= 5].index[0] if len(run[run >= 5]) else df.index[0]
    print(f"[{code}] 连续同价段:")
    print(df.loc[max(0,idx-5):idx, ["date","close","volume"]].tail(6).to_string(index=False))
