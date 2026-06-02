"""新浪日线源（后复权）——价量日线主力源"""
import pandas as pd
import akshare as ak
from lake.base import Fetcher, RateLimiter


class SinaDailyFetcher(Fetcher):
    """新浪 stock_zh_a_daily 后复权日线。回溯到各股上市日（start 控制下限）。"""

    def __init__(self, out_dir: str = "data_lake/price/daily",
                 start: str = "20100101", **kw):
        super().__init__(
            name="sina_daily",
            out_dir=out_dir,
            limiter=RateLimiter(min_interval=0.25, jitter=(0.1, 0.3)),
            max_workers=kw.pop("max_workers", 6),
            **kw,
        )
        self.start = start

    @staticmethod
    def to_sina(code: str):
        if code.startswith("6"):
            return "sh" + code        # 含688科创板
        if code.startswith(("0", "3")):
            return "sz" + code
        return None                    # 4/8北交所跳过

    def fetch_one(self, code: str):
        sym = self.to_sina(code)
        if sym is None:
            return None
        df = ak.stock_zh_a_daily(symbol=sym, start_date=self.start, adjust="hfq")
        if df is None or df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"])
        if "amount" not in df.columns:
            df["amount"] = df["volume"] * df["close"]
        keep = [c for c in ["date", "open", "close", "high", "low",
                            "volume", "amount", "turnover", "outstanding_share"]
                if c in df.columns]
        return df[keep].reset_index(drop=True)
