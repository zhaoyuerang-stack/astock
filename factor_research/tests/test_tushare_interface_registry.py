"""Tushare ingestion registry invariants."""
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.data.update_tushare import INTERFACES  # noqa: E402


def test_pledge_stat_uses_institutional_store_and_actual_fields():
    spec = INTERFACES["pledge_stat"]
    assert spec["store"] == "institutional/pledge_stat_all.parquet"
    assert spec["keys"] == ["ts_code", "end_date"]
    assert spec["fields"] == (
        "ts_code,end_date,pledge_count,unrest_pledge,rest_pledge,total_share,pledge_ratio"
    )
    print("✅ pledge_stat registry points to institutional store + actual source fields")


if __name__ == "__main__":
    test_pledge_stat_uses_institutional_store_and_actual_fields()
    print("\n🎉 tushare interface registry tests passed!")
