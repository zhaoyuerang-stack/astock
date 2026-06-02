"""最终校验：聚焦真数据质量问题（停牌/新股等归info不计入）"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
os.chdir(Path(__file__).parent)
import pandas as pd
from lake.validator import DataValidator

cal = pd.read_parquet("data_lake/meta/trade_calendar.parquet")["date"]
v = DataValidator(calendar=cal)
files = sorted(Path("data_lake/price/daily").glob("*.parquet"))
results = []
for i, fp in enumerate(files):
    results.append(v.validate(fp.stem, pd.read_parquet(fp)))
    if (i + 1) % 1500 == 0:
        print(f"  {i+1}/{len(files)}", flush=True)

report = v.quality_report(results, save_path="data_lake/quality_report.json")
print(f"\n=== 真实数据质量(聚焦真问题) ===", flush=True)
print(f"干净 {report['clean']}/{report['total']} ({report['clean_ratio']:.1%})", flush=True)
print(f"真问题分布: {report['issue_breakdown']}", flush=True)
info_cnt = sum(1 for r in results if r.get("info"))
print(f"有停牌/新股等信息标记: {info_cnt}只(A股正常现象)", flush=True)
