"""交易所融资融券源——个股明细，按交易日下载沪深合并（key=日期）"""
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
        df["date"] = pd.to_datetime(date_str)
        keep = ["date", "code", "margin_balance", "margin_buy", "short_balance", "short_vol"]
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
