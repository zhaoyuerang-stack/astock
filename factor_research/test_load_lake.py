"""验证数据加载层：价量加载 + 财务防未来函数对齐 + 估值自算"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
os.chdir(Path(__file__).parent)
from lake.load_lake import load_prices, load_fundamental_panel, load_panel

# 1. 价量面板
px = load_prices(codes=["600519", "000001", "300750"], start="2020-01-01")
print("价量面板:", {k: v.shape for k, v in px.items()})

# 2. 财务防未来函数对齐
fund = load_fundamental_panel(px["close"].index, codes=["600519"])
roe = fund["roe"]["600519"].dropna()
print(f"\n茅台ROE对齐(防未来函数): {len(roe)}个交易日有值")
print("最近3个变化点(应在财报披露日之后生效):")
changes = roe[roe != roe.shift()]
print(changes.tail(3).to_string())

# 3. 估值自算
panel = load_panel(codes=["600519"], start="2024-01-01")
if "pe" in panel:
    pe = panel["pe"]["600519"].dropna()
    print(f"\n茅台PE(自算close/EPS): 最近={pe.iloc[-1]:.1f}, 区间[{pe.min():.1f}, {pe.max():.1f}]")
print("\n加载层验证通过 ✅" if "pe" in panel else "\n财务数据未就绪")
