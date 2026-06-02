"""
下载全市场不复权close（估值PE/PB专用）—— 通达信mootdx原始价
（腾讯无真不复权、新浪py_mini_racer坏，只剩通达信可用）
mootdx单次800条，分批6次回溯2010。鲁棒+断点续传(已有则跳过)。
"""
import warnings; warnings.filterwarnings("ignore")
import os, threading
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import pandas as pd
from mootdx.quotes import Quotes
from lake.base import Fetcher, RateLimiter


class TdxRawFetcher(Fetcher):
    """通达信不复权日线close。单次800条，分批回溯到2010。"""
    def __init__(self, **kw):
        super().__init__(name="tdx_raw", out_dir="data_lake/price/daily_raw",
                         limiter=RateLimiter(0.05, (0, 0.05)),
                         max_workers=kw.pop("max_workers", 4), timeout=20, **kw)
        self._local = threading.local()

    @property
    def client(self):
        if not hasattr(self._local, "c"):
            self._local.c = Quotes.factory(market="std")
        return self._local.c

    def fetch_one(self, code):
        frames = []
        for b in range(6):                       # 6批×800 回溯到2010
            df = self.client.bars(symbol=code, frequency=9, start=b * 800, offset=800)
            if df is None or df.empty:
                break
            frames.append(df)
            if len(df) < 800:
                break
        if not frames:
            return None
        allf = pd.concat(frames).reset_index(drop=True)
        allf["date"] = pd.to_datetime(allf["datetime"]).dt.floor("D")
        out = (allf[["date", "close"]].rename(columns={"close": "raw_close"})
               .drop_duplicates("date").sort_values("date"))
        out = out[out["date"] >= pd.Timestamp("2010-01-01")].reset_index(drop=True)
        return out if len(out) else None


if __name__ == "__main__":
    codes = sorted(fp.stem for fp in Path("data_lake/price/daily").glob("*.parquet"))
    print(f"通达信下载不复权close: {len(codes)}只", flush=True)
    f = TdxRawFetcher()
    stats = f.run(codes)
    if stats["failures"]:
        f.retry_failures(stats["failures"])
    print(f"✅ 不复权close: {len(list(Path('data_lake/price/daily_raw').glob('*.parquet')))}只", flush=True)
