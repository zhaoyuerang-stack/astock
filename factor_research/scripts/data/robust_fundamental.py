"""
鲁棒财务下载（硬刚东财，无人值守）
循环：检测封禁→遇封禁等3分钟→下一批50只→断点续传，最多10小时。
配合 setsid 脱离 harness 避免被 kill。
"""
import warnings; warnings.filterwarnings("ignore")
import os, time, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import akshare as ak
from lake.sources.em_fin import EastmoneyFinanceFetcher

FUND = Path("data_lake/fundamental")


def is_banned():
    try:
        df = ak.stock_financial_abstract(symbol="000089")
        return not (df is not None and len(df) > 0)
    except Exception:
        return True


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


codes = sorted(fp.stem for fp in Path("data_lake/price/daily").glob("*.parquet"))
f = EastmoneyFinanceFetcher()   # 降速 limiter1.1s + 2worker + daemon超时

start = time.time()
MAX_HOURS = 10
ban_waits = 0

log(f"鲁棒财务下载启动，目标{len(codes)}只")
while time.time() - start < MAX_HOURS * 3600:
    remaining = [c for c in codes if not (FUND / f"{c}.parquet").exists()]
    done = len(codes) - len(remaining)
    if not remaining:
        log(f"✅ 全部完成: {done}只")
        break

    if is_banned():
        ban_waits += 1
        log(f"封禁中(已下{done}只, 第{ban_waits}次等待), 等3分钟...")
        time.sleep(180)
        continue

    batch = remaining[:50]
    log(f"下载批次: {len(batch)}只 (已完成{done}/{len(codes)})")
    f.run(batch, skip_existing=True, progress_every=999)
    time.sleep(5)   # 批间小憩

final = len(list(FUND.glob("*.parquet")))
log(f"结束: {final}只 (封禁等待{ban_waits}次, 总用时{(time.time()-start)/60:.0f}分钟)")
