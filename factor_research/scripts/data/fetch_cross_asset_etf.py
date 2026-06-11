"""Fetch cross-asset ETF daily data into data_lake/cross_asset/etf/.

5 个核心 ETF (按 ROADMAP 阶段 5 Phase 2.1):
  511010  国债 ETF        利率敏感, 与股票 corr ~0
  518880  黄金 ETF        通胀/避险, 与股票 corr <0.2
  159920  恒生 ETF        港股暴露, 已 HK 实证 corr 0.26
  510880  红利 ETF        价值大盘, 与小盘 corr ~0.5
  513100  纳指 ETF        美股暴露, 与 A 股 corr <0.3

数据源: akshare.fund_etf_hist_em (东财)
存储: data_lake/cross_asset/etf/{code}.parquet
列: date,open,close,high,low,volume,amount (后复权, 轮动回测用)
    + raw_open,raw_close,raw_high,raw_low (不复权, 模拟盘成交/估值/跟单展示用,
      与 daily_raw 同口径 —— 人在券商 App 看到的就是这个价)

用法:
  全量重抓: /usr/bin/python3 -m scripts.data.fetch_cross_asset_etf
  增量(供 scheduled_daily_update 调用): from scripts.data.fetch_cross_asset_etf import update_etfs
"""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import time
from datetime import datetime, timedelta

import pandas as pd

OUT = ROOT / "data_lake" / "cross_asset" / "etf"

ETFS = {
    "511010": "国债 ETF",
    "518880": "黄金 ETF",
    "159920": "恒生 ETF",
    "510880": "红利 ETF",
    "513100": "纳指 ETF",
}

START = "20100101"
END = "20261231"

_RENAME = {
    "日期": "date", "开盘": "open", "收盘": "close",
    "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "amount",
}
_RAW_RENAME = {"open": "raw_open", "close": "raw_close", "high": "raw_high", "low": "raw_low"}


def _fetch(code, start, end, adjust):
    """单次抓取并标准化列;失败抛异常由调用方处理。"""
    import akshare as ak
    df = ak.fund_etf_hist_em(symbol=code, period="daily",
                             start_date=start, end_date=end, adjust=adjust)
    df = df.rename(columns={k: v for k, v in _RENAME.items() if k in df.columns})
    cols = [c for c in ["date", "open", "close", "high", "low", "volume", "amount"] if c in df.columns]
    df = df[cols]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def fetch_one(code, start=START, end=END):
    """抓单只 ETF:后复权 + 不复权合并(raw_* 列),按 date 对齐。"""
    hfq = _fetch(code, start, end, adjust="hfq")
    time.sleep(0.3)  # 避免封禁
    raw = _fetch(code, start, end, adjust="")
    raw = raw[["date", "open", "close", "high", "low"]].rename(columns=_RAW_RENAME)
    return hfq.merge(raw, on="date", how="left")


def update_etfs(codes=None, lookback_days=30):
    """增量更新 ETF 日线(供 scheduled_daily_update 每日调用)。

    现存文件缺 raw_close 列(旧格式只有后复权)→ 全量重抓补齐口径;
    否则只抓最近 lookback_days 自然日窗口并 merge(drop_duplicates keep=last)。
    返回 {code: {"ok": bool, "rows": n, "latest": "YYYY-MM-DD"} | {"ok": False, "error": ...}}
    """
    OUT.mkdir(parents=True, exist_ok=True)
    codes = codes or list(ETFS)
    stats = {}
    for code in codes:
        fp = OUT / f"{code}.parquet"
        try:
            old = pd.read_parquet(fp) if fp.exists() else None
            if old is None or "raw_close" not in old.columns:
                new = fetch_one(code)            # 全量(首次/旧格式补 raw 列)
            else:
                start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d")
                inc = fetch_one(code, start=start)
                new = (pd.concat([old, inc]).drop_duplicates("date", keep="last")
                       .sort_values("date").reset_index(drop=True))
            new.to_parquet(fp)
            latest = str(new["date"].max().date())
            stats[code] = {"ok": True, "rows": len(new), "latest": latest}
            print(f"  [etf] {code} {ETFS.get(code, '')}: {len(new)} rows → {latest}", flush=True)
        except Exception as e:
            stats[code] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:80]}"}
            print(f"  [etf] {code} ⚠ {stats[code]['error']}", flush=True)
        time.sleep(0.3)
    return stats


def main():
    print(f"Fetching {len(ETFS)} ETFs (full, hfq + raw) to {OUT}")
    print(f"  Period: {START} ~ {END}")
    OUT.mkdir(parents=True, exist_ok=True)
    for code, name in ETFS.items():
        print(f"\n[{code}] {name}", flush=True)
        try:
            df = fetch_one(code)
            fp = OUT / f"{code}.parquet"
            df.to_parquet(fp)
            print(f"  ✓ {df.shape}  {df['date'].min().date()} ~ {df['date'].max().date()}  → {fp.name}")
        except Exception as e:
            print(f"  ⚠ {type(e).__name__}: {str(e)[:80]}")
        time.sleep(0.3)
    print(f"\nDone. Files in {OUT}:")
    for fp in sorted(OUT.glob("*.parquet")):
        print(f"  {fp.name}: {fp.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
