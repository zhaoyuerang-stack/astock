"""下载全市场财务数据（东财摘要，回溯1998，防未来函数）"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
from lake.sources.em_fin import EastmoneyFinanceFetcher

codes = sorted(fp.stem for fp in Path("data_lake/price/daily").glob("*.parquet"))
print(f"财务下载: {len(codes)}只", flush=True)

f = EastmoneyFinanceFetcher()  # 默认6 worker + limiter0.35 + 超时20s
stats = f.run(codes)
if stats["failures"]:
    print(f"重试 {len(stats['failures'])} 个失败...", flush=True)
    f.retry_failures(stats["failures"])

n = len(list(Path("data_lake/fundamental").glob("*.parquet")))
print(f"财务数据完成: {n}只", flush=True)
