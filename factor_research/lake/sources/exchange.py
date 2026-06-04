"""交易所/互联互通资金面源。

两融按交易日下载沪深个股明细。北向持股来自东财每日个股统计；
若本机代理拦截 eastmoney，会记录失败，等待网络直连规则恢复后断点续传。
"""
import akshare as ak
import pandas as pd
from lake.base import Fetcher, RateLimiter

# 沪深字段名差异 → 统一英文
RENAME = {
    "标的证券代码": "code", "证券代码": "code",
    "融资余额": "margin_balance", "融资买入额": "margin_buy",
    "融券余量": "short_vol", "融券余额": "short_balance",
    "融券卖出量": "short_sell",
}

NORTHBOUND_RENAME = {
    "持股日期": "date",
    "股票代码": "code",
    "股票简称": "name",
    "当日收盘价": "close",
    "当日涨跌幅": "pct_chg",
    "持股数量": "northbound_hold_shares",
    "持股市值": "northbound_hold_value",
    "持股数量占发行股百分比": "northbound_hold_pct",
    "持股市值变化-1日": "northbound_value_chg_1d",
    "持股市值变化-5日": "northbound_value_chg_5d",
    "持股市值变化-10日": "northbound_value_chg_10d",
}


def _to_numeric(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


class MarginFetcher(Fetcher):
    """
    个股两融明细，按交易日下载（沪+深合并）。key 是日期字符串 'YYYYMMDD'。
    两融2010-03推出，遍历交易日历下载。
    """
    def __init__(self, out_dir: str = "data_lake/capital/margin", **kw):
        super().__init__(
            name="margin", out_dir=out_dir,
            limiter=RateLimiter(min_interval=0.4, jitter=(0.1, 0.3)),
            max_workers=kw.pop("max_workers", 4), **kw,
        )

    def out_path(self, key: str):
        return self.out_dir / f"{key}.parquet"

    def fetch_one(self, date_str: str):
        frames = []
        for src in (ak.stock_margin_detail_sse, ak.stock_margin_detail_szse):
            try:
                d = src(date=date_str)
                if d is not None and len(d):
                    d = d.rename(columns=RENAME)
                    if "code" in d.columns:
                        d["code"] = d["code"].astype(str).str.zfill(6)
                        frames.append(d)
            except Exception:
                continue
        if not frames:
            return None
        df = pd.concat(frames, ignore_index=True)
        df = _to_numeric(
            df,
            ["margin_balance", "margin_buy", "short_balance", "short_vol", "short_sell"],
        )
        df["date"] = pd.to_datetime(date_str)
        keep = ["date", "code", "margin_balance", "margin_buy", "short_balance", "short_vol"]
        return df[[c for c in keep if c in df.columns]]


class NorthboundFetcher(Fetcher):
    """北向持股每日个股统计，key 是日期字符串 'YYYYMMDD'。"""

    def __init__(self, out_dir: str = "data_lake/capital/northbound", **kw):
        super().__init__(
            name="northbound", out_dir=out_dir,
            limiter=RateLimiter(min_interval=1.0, jitter=(0.3, 0.8)),
            max_workers=kw.pop("max_workers", 1), **kw,
        )

    def out_path(self, key: str):
        return self.out_dir / f"{key}.parquet"

    def fetch_one(self, date_str: str):
        df = ak.stock_hsgt_stock_statistics_em(
            symbol="北向持股",
            start_date=date_str,
            end_date=date_str,
        )
        if df is None or df.empty:
            return None
        df = df.rename(columns=NORTHBOUND_RENAME)
        if "code" not in df.columns:
            return None
        df["code"] = df["code"].astype(str).str.zfill(6)
        df["date"] = pd.to_datetime(df["date"])
        df = _to_numeric(df, [
            "close", "pct_chg", "northbound_hold_shares", "northbound_hold_value",
            "northbound_hold_pct", "northbound_value_chg_1d",
            "northbound_value_chg_5d", "northbound_value_chg_10d",
        ])
        keep = [
            "date", "code", "northbound_hold_shares", "northbound_hold_value",
            "northbound_hold_pct", "northbound_value_chg_1d",
            "northbound_value_chg_5d", "northbound_value_chg_10d",
        ]
        return df[[c for c in keep if c in df.columns]]


def merge_margin(margin_dir: str = "data_lake/capital/margin",
                 out: str = "data_lake/capital/margin_all.parquet"):
    """把按日期的两融文件合并成一个长表 (date×code)"""
    from pathlib import Path
    files = sorted(Path(margin_dir).glob("*.parquet"))
    if not files:
        return None
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df.to_parquet(out, index=False)
    print(f"[margin] 合并 {len(files)}个交易日 → {len(df)}行")
    return df


def merge_northbound(northbound_dir: str = "data_lake/capital/northbound",
                     out: str = "data_lake/capital/northbound_all.parquet"):
    """把按日期的北向文件合并成一个长表 (date×code)。"""
    from pathlib import Path
    files = sorted(Path(northbound_dir).glob("*.parquet"))
    if not files:
        return None
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df.to_parquet(out, index=False)
    print(f"[northbound] 合并 {len(files)}个交易日 → {len(df)}行")
    return df
