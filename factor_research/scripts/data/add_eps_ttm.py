"""给财务批量表加 TTM EPS（修对PE：累计EPS→单季→滚动4季TTM）"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import pandas as pd

fp = Path("data_lake/fundamental_batch.parquet")
df = pd.read_parquet(fp).sort_values(["code", "report_date"]).reset_index(drop=True)
df["q"] = df["report_date"].dt.quarter

# 单季EPS：Q1=累计本身；Q2/Q3/Q4=本期累计 - 上期累计（同年内）
df["eps_single"] = df.groupby("code")["eps"].diff()
df.loc[df["q"] == 1, "eps_single"] = df.loc[df["q"] == 1, "eps"]

# TTM = 滚动最近4个单季之和（年报四季完整时=全年EPS）
df["eps_ttm"] = df.groupby("code")["eps_single"].transform(lambda x: x.rolling(4, min_periods=4).sum())
# 同理净利润TTM
if "net_profit" in df.columns:
    df["np_single"] = df.groupby("code")["net_profit"].diff()
    df.loc[df["q"] == 1, "np_single"] = df.loc[df["q"] == 1, "net_profit"]
    df["net_profit_ttm"] = df.groupby("code")["np_single"].transform(lambda x: x.rolling(4, min_periods=4).sum())

df = df.drop(columns=["q", "eps_single"] + (["np_single"] if "np_single" in df.columns else []))
df.to_parquet(fp, index=False)

# 验证茅台
mt = df[df["code"] == "600519"].dropna(subset=["eps_ttm"]).tail(2)
print("茅台TTM EPS(应~70全年):", mt[["report_date", "eps", "eps_ttm"]].to_string(index=False), flush=True)
print(f"✅ 已加 eps_ttm/net_profit_ttm 到 fundamental_batch", flush=True)
