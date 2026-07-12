"""数据湖写入口守卫回归测试。"""
import sys
from pathlib import Path

import pytest

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


def test_flags_direct_global_raw_write_outside_lake_layer():
    src = """
from pathlib import Path
store = Path("data_lake") / "global_raw" / "alfred_macro_v1"
raw.to_parquet(store / "payload.parquet")
"""
    assert scan_source(src, rel="workflow/global_probe.py") == ["workflow/global_probe.py"]


def test_flags_feather_and_pickle_writers():
    feather = '''
from pathlib import Path
target = Path("data_lake") / "price" / "daily.feather"
frame.to_feather(target)
'''
    pickled = '''
from pathlib import Path
target = Path("data_lake") / "meta" / "snapshot.pkl"
frame.to_pickle(target)
'''
    assert scan_source(feather, rel="workflow/export.py") == ["workflow/export.py"]
    assert scan_source(pickled, rel="workflow/export.py") == ["workflow/export.py"]


def test_test_code_cannot_write_the_real_lake():
    src = '''
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "data_lake" / "price" / "daily.parquet"
frame.to_parquet(target)
'''
    assert scan_source(src, rel="tests/test_bad_selftest.py") == ["tests/test_bad_selftest.py"]


def test_test_code_may_write_a_temp_lake_fixture():
    src = '''
lake = tmp_path / "data_lake"
target = lake / "price" / "daily.parquet"
frame.to_parquet(target)
'''
    assert scan_source(src, rel="tests/test_fixture.py") == []


def test_flags_alias_chain_path_construction():
    src = '''
from pathlib import Path
LAKE = Path("data_lake")
core = LAKE / "price"
target = core / "daily.parquet"
frame.to_parquet(target)
'''
    assert scan_source(src, rel="workflow/export.py") == ["workflow/export.py"]


def test_flags_path_open_write_mode_and_allows_temp_fixture():
    production = '''
from pathlib import Path
target = Path("data_lake") / "price" / "manual.csv"
with target.open("w", encoding="utf-8") as stream:
    stream.write("bad")
'''
    fixture = '''
target = tmp_path / "data_lake" / "price" / "fixture.csv"
with target.open(mode="x", encoding="utf-8") as stream:
    stream.write("ok")
'''
    assert scan_source(production, rel="workflow/export.py") == ["workflow/export.py"]
    assert scan_source(fixture, rel="tests/test_fixture.py") == []


@pytest.mark.parametrize("area", ["financials", "daily_basic", "holder", "governance", "agent"])
def test_entire_data_lake_is_protected(area):
    src = f'''
from pathlib import Path
target = Path("data_lake") / "{area}" / "payload.json"
target.write_text("bad")
'''
    assert scan_source(src, rel="workflow/export.py") == ["workflow/export.py"]


def test_flags_keyword_destination_argument():
    src = '''
from pathlib import Path
p = Path("data_lake") / "financials" / "income.parquet"
frame.to_parquet(path=p)
'''
    assert scan_source(src, rel="workflow/export.py") == ["workflow/export.py"]


def test_allows_only_an_explicit_negative_runtime_barrier_assertion_in_tests():
    expected_block = '''
from pathlib import Path
target = Path("data_lake") / "price" / "must_not_land.parquet"
with pytest.raises(RuntimeError, match="canonical data_lake forbidden"):
    frame.to_parquet(target)
'''
    weak_assertion = expected_block.replace("canonical data_lake forbidden", "something")
    assert scan_source(expected_block, rel="tests/test_runtime_barrier.py") == []
    assert scan_source(weak_assertion, rel="tests/test_runtime_barrier.py") == [
        "tests/test_runtime_barrier.py"
    ]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
