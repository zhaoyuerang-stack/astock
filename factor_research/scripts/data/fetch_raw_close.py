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
    """通达信不复权日线 OHLC。全量:6批×800 回溯2010;增量:只拉最近 inc_offset 条并 merge 现有。"""
    COLS = {"open": "raw_open", "high": "raw_high", "low": "raw_low", "close": "raw_close"}

    def __init__(self, incremental=False, inc_offset=20, **kw):
        super().__init__(name="tdx_raw", out_dir="data_lake/price/daily_raw",
                         limiter=RateLimiter(0.05, (0, 0.05)),
                         max_workers=kw.pop("max_workers", 4), timeout=20, **kw)
        self.incremental = incremental
        self.inc_offset = inc_offset
        self._local = threading.local()

    @property
    def client(self):
        if not hasattr(self._local, "c"):
            self._local.c = Quotes.factory(market="std")
        return self._local.c

    def _to_ohlc(self, frames):
        allf = pd.concat(frames).reset_index(drop=True)
        allf["date"] = pd.to_datetime(allf["datetime"]).dt.floor("D")
        out = (allf[["date"] + list(self.COLS)].rename(columns=self.COLS)
               .drop_duplicates("date").sort_values("date"))
        return out[out["date"] >= pd.Timestamp("2010-01-01")].reset_index(drop=True)

    def fetch_one(self, code):
        if self.incremental:                      # 增量:最近 inc_offset 条 + merge 现有
            df = self.client.bars(symbol=code, frequency=9, start=0, offset=self.inc_offset)
            if df is None or df.empty:
                return None
            new = self._to_ohlc([df])
            fp = self.out_path(code)
            if fp.exists():
                old = pd.read_parquet(fp)
                new = (pd.concat([old, new]).drop_duplicates("date", keep="last")
                       .sort_values("date").reset_index(drop=True))
            return new if len(new) else None
        frames = []                               # 全量:6批×800 回溯2010
        for b in range(6):
            df = self.client.bars(symbol=code, frequency=9, start=b * 800, offset=800)
            if df is None or df.empty:
                break
            frames.append(df)
            if len(df) < 800:
                break
        return self._to_ohlc(frames) if frames else None


def update_raw_prices(inc_offset=20, max_workers=4):
    """增量更新全市场 daily_raw 到最新(带 OHLC),消除 raw 滞后(供每日 daily_update 调用)。

    更新个股文件后重建 daily_raw_all.parquet，保证 load_raw_close() 读大表时不滞后。
    （对应 update_prices() 更新 daily 后调用 compact_prices() 的逻辑。）
    """
    codes = sorted(fp.stem for fp in Path("data_lake/price/daily_raw").glob("*.parquet"))
    print(f"通达信增量更新不复权 OHLC: {len(codes)}只", flush=True)
    f = TdxRawFetcher(incremental=True, inc_offset=inc_offset, max_workers=max_workers)
    stats = f.run(codes, skip_existing=False)
    if stats.get("failures"):
        f.retry_failures(stats["failures"])
    print(f"[raw] 增量完成 ok={stats['ok']} empty={stats['empty']} err={stats['error']}", flush=True)

    # 重建大表（load_raw_close 优先读 daily_raw_all.parquet，不重建则滞后一日）
    if stats.get("ok", 0) > 0:
        from lake.compact import compact_raw_prices
        compact_raw_prices("data_lake/price/daily_raw", "data_lake/price/daily_raw_all.parquet")

    return stats


if __name__ == "__main__":
    import sys
    if "--incremental" in sys.argv:
        update_raw_prices()
    else:
        codes = sorted(fp.stem for fp in Path("data_lake/price/daily").glob("*.parquet"))
        print(f"通达信全量下载不复权 OHLC: {len(codes)}只", flush=True)
        f = TdxRawFetcher()
        stats = f.run(codes, skip_existing=False)   # 强制重拉,补全历史 OHLC(旧文件只有 raw_close)
        if stats["failures"]:
            f.retry_failures(stats["failures"])
        print(f"✅ 不复权 OHLC: {len(list(Path('data_lake/price/daily_raw').glob('*.parquet')))}只", flush=True)
        # 全量重建大表
        from lake.compact import compact_raw_prices
        compact_raw_prices("data_lake/price/daily_raw", "data_lake/price/daily_raw_all.parquet")
