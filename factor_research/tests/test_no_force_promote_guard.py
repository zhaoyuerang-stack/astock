"""check_no_force_promote 守卫的 fixture 测试 + 实跑实库。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci.check_no_force_promote import scan_source, check


def test_flags_force_true():
    src = "def f():\n    return promote_hypothesis(h, force=True)\n"
    v = scan_source(src, "x")
    assert len(v) == 1 and "force=True" in v[0]


def test_flags_run_marginal_false():
    src = "promote_pool_l3(version='v1.0', run_marginal=False)\n"
    v = scan_source(src, "x")
    assert len(v) == 1 and "run_marginal=False" in v[0]


def test_clean_passes():
    src = "promote_hypothesis(h, force=False, run_marginal=True, run_nine_gate=True)\n"
    assert scan_source(src, "x") == []


def test_force_false_not_flagged():
    src = "register(fam, ver, force=False)\n"
    assert scan_source(src, "x") == []


def test_live_repo_clean():
    # bulk_promote / factory_cli / scheduled_factor_search / autoresearch 入口无字面 force=True
    assert check() == 0


def test_scan_set_covers_factory_cli():
    from scripts.ci.check_no_force_promote import AUTO_PROMOTE_FILES

    assert "apps/factory_cli.py" in AUTO_PROMOTE_FILES
    assert "services/actions/autoresearch.py" in AUTO_PROMOTE_FILES


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
