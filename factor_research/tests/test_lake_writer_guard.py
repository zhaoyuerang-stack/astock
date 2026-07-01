"""数据湖写入口守卫回归测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci.check_lake_writers import scan_source


def test_flags_direct_version_returns_csv_write_outside_lake_layer():
    src = """
from pathlib import Path
store = Path("data_lake") / "version_returns"
rets.to_csv(store / "family__v1.csv")
"""
    violations = scan_source(src, rel="workflow/promote_composite.py")
    assert violations == ["workflow/promote_composite.py"]


def test_allows_canonical_lake_writer_for_version_returns():
    src = """
from pathlib import Path
store = Path("data_lake") / "version_returns"
rets.to_csv(store / "family__v1.csv")
"""
    assert scan_source(src, rel="lake/version_returns.py") == []


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
