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


def test_legacy_version_returns_direct_write_fixture_fails_guard(tmp_path):
    """模拟老直写路径 fixture 在 lake 守卫下必红(审计 #5 销账后无 PENDING 庇护)。"""
    from scripts.ci import check_lake_writers as guard

    # 局部 PENDING 清空:销账后直写 version_returns 即硬红
    orig = dict(guard.PENDING_REMEDIATION)
    guard.PENDING_REMEDIATION.clear()
    try:
        rogue = tmp_path / "workflow"
        rogue.mkdir()
        (rogue / "promote_composite.py").write_text(
            "store = ROOT / 'data_lake' / 'version_returns'\n"
            "store.mkdir(parents=True, exist_ok=True)\n"
            "rets.to_csv(store / 'composite-portfolio__v1.csv', header=True)\n",
            encoding="utf-8",
        )
        research = tmp_path / "scripts" / "research"
        research.mkdir(parents=True)
        (research / "run_nine_gates_all.py").write_text(
            "store = Path('data_lake/version_returns')\n"
            "rets.rename('ret').to_csv(store / f'{fam}__{ver}.csv', header=True)\n",
            encoding="utf-8",
        )
        assert main(tmp_path) == 1
        hits = scan(tmp_path)
        assert "workflow/promote_composite.py" in hits
        assert "scripts/research/run_nine_gates_all.py" in hits
    finally:
        guard.PENDING_REMEDIATION.update(orig)


def test_migrated_writers_produce_valid_sidecar(tmp_path):
    """迁移后写路径产出合法 sidecar(hermetic,不跑真数据)。"""
    import pandas as pd
    from lake.version_returns import (
        config_hash,
        load_verified_version_returns,
        write_version_returns,
    )

    idx = pd.bdate_range("2020-01-02", periods=5)
    rets = pd.Series([0.01, -0.02, 0.005, 0.0, 0.003], index=idx)

    # 模拟 run_nine_gates_all --persist(有 spec_hash)
    p1 = write_version_returns(
        "small-cap-size", "v2.0", rets,
        source="run_nine_gates_all --persist",
        spec_hash="spec-nine-gates-fixture",
        data_fingerprint="fp-hermetic",
        cost_hash="cost-hermetic",
        root=tmp_path,
    )
    assert p1["identity_tier"] == "spec"
    assert p1["source"] == "run_nine_gates_all --persist"
    s1, pr1, r1 = load_verified_version_returns(
        "small-cap-size", "v2.0", root=tmp_path,
    )
    assert r1 == "" and s1 is not None and pr1["series_hash"] == p1["series_hash"]

    # 模拟 promote_composite(config-only)
    p2 = write_version_returns(
        "composite-portfolio", "v1.0", rets,
        source="promote_composite",
        config_hash=config_hash({"allocation": {"a": 0.4}, "rebalance_days": 1}),
        data_fingerprint="fp-hermetic",
        cost_hash="cost-hermetic",
        root=tmp_path,
    )
    assert p2["identity_tier"] == "config-only"
    assert p2["source"] == "promote_composite"
    s2, pr2, r2 = load_verified_version_returns(
        "composite-portfolio", "v1.0", root=tmp_path,
    )
    assert r2 == "" and s2 is not None and pr2["identity_tier"] == "config-only"


def test_pending_no_longer_lists_migrated_version_returns_writers():
    """销账:PENDING 不得再庇护 promote_composite / run_nine_gates_all。"""
    from scripts.ci.check_lake_writers import PENDING_REMEDIATION

    assert "workflow/promote_composite.py" not in PENDING_REMEDIATION
    assert "scripts/research/run_nine_gates_all.py" not in PENDING_REMEDIATION


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
