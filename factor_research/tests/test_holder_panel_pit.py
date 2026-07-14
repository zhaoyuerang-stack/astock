"""股东户数(holdernumber)PIT 防未来回归测试(#5 第一个独立数据族 island)。

铁律2:T 日只用 ann_date ≤ T 已公告的数据。这是 #5 接 holder 进 DSL 的地基,
PIT 错=整个独立数据族 alpha 作废,故单独锁死。

口径:load_tushare_panel("holdernumber") 走 canonical ffill_by_anndate(ann_date 生效 ffill)。
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.requires_data_lake

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lake.load_lake import load_tushare_panel

_FP = ROOT / "data_lake" / "holder" / "holdernumber_all.parquet"


def test_holder_panel_pit_no_future_leak():
    # 000001.SZ 已知公告点:ann 20250823→443583(end 0630),ann 20251025→453515(end 0930)
    trade = pd.bdate_range("2025-08-01", "2025-11-15")
    s = load_tushare_panel("holdernumber", trade, codes=["000001"])["holder_num"]["000001"]

    def asof(d):
        dt = pd.Timestamp(d)
        sub = s.loc[:dt].dropna()
        return sub.iloc[-1] if len(sub) else None

    # 公告后生效
    assert asof("2025-08-25") == 443583.0, "0823 公告后应=443583"
    assert asof("2025-10-28") == 453515.0, "1025 公告后应=453515"
    # 关键:公告前不得泄露未来值
    assert asof("2025-10-20") == 443583.0, "1025 公告前不得已是 453515(未来泄漏)"
    assert asof("2025-08-20") != 443583.0, "0823 公告前不得已是 443583(未来泄漏)"


if __name__ == "__main__":
    test_holder_panel_pit_no_future_leak()
    print("✅ holder panel PIT 防未来 通过")
