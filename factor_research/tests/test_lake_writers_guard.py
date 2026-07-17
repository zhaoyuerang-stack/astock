"""check_lake_writers 守卫对抗测试(审计 #4)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci.check_lake_writers import (
    file_is_violation,
    main,
    scan,
)


def test_financials_to_csv_flagged():
    """盲区目录 data_lake/financials + to_csv 组合必红。"""
    src = (
        "from pathlib import Path\n"
        "p = Path('data_lake/financials/income.parquet')\n"
        "df.to_csv(p)\n"
    )
    assert file_is_violation(src)


def test_path_component_data_lake_to_csv_flagged():
    """Path 组件式 ROOT / 'data_lake' / 'version_returns' + to_csv 必红。"""
    src = (
        "store = ROOT / 'data_lake' / 'version_returns'\n"
        "rets.to_csv(store / 'x.csv')\n"
    )
    assert file_is_violation(src)


def test_to_pickle_and_write_table_flagged():
    assert file_is_violation("df.to_pickle('data_lake/event/x.pkl')\n")
    assert file_is_violation("import pyarrow as pa\nwrite_table(t, 'data_lake/meta/x')\n")


def test_lake_package_write_allowed_via_prefix(tmp_path):
    """lake/ 内的写必绿(ALLOWED_PREFIXES)。"""
    lake = tmp_path / "lake"
    lake.mkdir()
    (lake / "writer.py").write_text(
        "df.to_parquet('data_lake/price/daily_all.parquet')\n",
        encoding="utf-8",
    )
    assert main(tmp_path) == 0


def test_read_parquet_not_flagged():
    """读路径(read_parquet)不误报。"""
    src = "df = pd.read_parquet('data_lake/price/daily_all.parquet')\nprint(df)\n"
    assert not file_is_violation(src)


def test_rogue_writer_outside_allowed_fails(tmp_path):
    """非允许前缀目录写湖 → 守卫失败。"""
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "evil.py").write_text(
        "df.to_csv('data_lake/holder/x.csv')\n",
        encoding="utf-8",
    )
    assert main(tmp_path) == 1
    assert "apps/evil.py" in scan(tmp_path)


def test_live_repo_clean_with_pending():
    """真实仓库:存量在 PENDING → 无新增即绿。"""
    assert main() == 0


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
