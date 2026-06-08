"""Fetch cross-asset ETF daily data into data_lake/cross_asset/etf/.

5 个核心 ETF (按 ROADMAP 阶段 5 Phase 2.1):
  511010  国债 ETF        利率敏感, 与股票 corr ~0
  518880  黄金 ETF        通胀/避险, 与股票 corr <0.2
  159920  恒生 ETF        港股暴露, 已 HK 实证 corr 0.26
  510880  红利 ETF        价值大盘, 与小盘 corr ~0.5
  513100  纳指 ETF        美股暴露, 与 A 股 corr <0.3

数据源: akshare.fund_etf_hist_em (东财, 后复权)
存储: data_lake/cross_asset/etf/{code}.parquet (列: date,open,close,high,low,volume,amount)

用法: /usr/bin/python3 -m scripts.data.fetch_cross_asset_etf
"""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import time
import pandas as pd
import akshare as ak

OUT = ROOT / "data_lake" / "cross_asset" / "etf"
OUT.mkdir(parents=True, exist_ok=True)

ETFS = {
    "511010": "国债 ETF",
    "518880": "黄金 ETF",
    "159920": "恒生 ETF",
    "510880": "红利 ETF",
    "513100": "纳指 ETF",
}

START = "20100101"
END = "20261231"

print(f"Fetching {len(ETFS)} ETFs to {OUT}")
print(f"  Period: {START} ~ {END}")

for code, name in ETFS.items():
    print(f"\n[{code}] {name}", flush=True)
    try:
        # ETF 历史 (复权后)
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=START,
            end_date=END,
            adjust="hfq",   # 后复权
        )
        # 标准化列名 (东财返回中文)
        rename_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low",
            "成交量": "volume", "成交额": "amount",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        cols = [c for c in ["date", "open", "close", "high", "low", "volume", "amount"] if c in df.columns]
        df = df[cols]
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        fp = OUT / f"{code}.parquet"
        df.to_parquet(fp)
        print(f"  ✓ {df.shape}  {df['date'].min().date()} ~ {df['date'].max().date()}  → {fp.name}")
    except Exception as e:
        print(f"  ⚠ {type(e).__name__}: {str(e)[:80]}")
    time.sleep(0.3)   # 避免封禁

print(f"\nDone. Files in {OUT}:")
for fp in sorted(OUT.glob("*.parquet")):
    print(f"  {fp.name}: {fp.stat().st_size // 1024} KB")
