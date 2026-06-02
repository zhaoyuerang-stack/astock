"""自动等东财封禁解除 + 降速全量财务下载（无人值守）"""
import warnings; warnings.filterwarnings("ignore")
import os, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import akshare as ak
from lake.sources.em_fin import EastmoneyFinanceFetcher

# 1. 循环等封禁解除（每3分钟测一次，最多60分钟）
print("等待东财封禁解除...", flush=True)
lifted = False
for i in range(20):
    try:
        df = ak.stock_financial_abstract(symbol="000089")
        if df is not None and len(df) > 0:
            print(f"✅ 封禁解除(等了{i*3}分钟)，启动降速下载", flush=True)
            lifted = True
            break
    except Exception:
        pass
    print(f"  封禁中(已等{i*3}分钟)，再等3分钟...", flush=True)
    time.sleep(180)

if not lifted:
    print("⚠️ 等待60分钟封禁仍未解除，退出", flush=True)
    raise SystemExit

# 2. 降速全量财务下载（limiter1.1s+2worker+daemon超时，断点续传）
codes = sorted(fp.stem for fp in Path("data_lake/price/daily").glob("*.parquet"))
print(f"降速下载财务: {len(codes)}只 (预计~1.5小时)", flush=True)
f = EastmoneyFinanceFetcher()
stats = f.run(codes)
if stats["failures"]:
    print(f"重试{len(stats['failures'])}个失败...", flush=True)
    time.sleep(30)
    f.retry_failures(stats["failures"])

n = len(list(Path("data_lake/fundamental").glob("*.parquet")))
print(f"✅ 财务下载完成: {n}只", flush=True)
