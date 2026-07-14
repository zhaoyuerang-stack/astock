"""check_no_force_promote 守卫的 fixture 测试 + 实跑实库。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci.check_no_force_promote import (
    check,
    discover_auto_promote_files,
    scan_source,
)


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
    # bulk_promote 已修硬闸 → 实库应通过
    assert check() == 0


def test_known_auto_promoters_still_discovered():
    """默认扫描至少覆盖原枚举名单里的两个已知自动晋级脚本。"""
    rels = {str(p).split("factor_research/")[-1] for p in discover_auto_promote_files()}
    assert "scripts/ops/bulk_promote.py" in rels
    assert "scripts/ops/scheduled_factor_search.py" in rels


def test_new_auto_promoter_auto_scanned(tmp_path):
    """对抗性回归(2026-07-11 加固):新增自动晋级脚本必须被自动纳入扫描。

    旧代码用人工枚举名单,新脚本默认逃逸——本测试在旧代码上失败
    (旧代码无 discover_auto_promote_files,import 即炸;语义上也不会发现新文件)。
    """
    ops = tmp_path / "scripts" / "ops"
    ops.mkdir(parents=True)
    evil = ops / "evil_promote.py"
    evil.write_text(
        "from workflow.promote import promote_pool_l3\n"
        "promote_pool_l3(version='v1.0', force=True)\n",
        encoding="utf-8",
    )
    (ops / "innocent.py").write_text("print('no promote here')\n", encoding="utf-8")

    found = discover_auto_promote_files(tmp_path)
    assert evil in found, "import 晋级通道的新脚本必须被默认扫描发现"
    assert (ops / "innocent.py") not in found

    assert check(tmp_path) == 1, "含 force=True 的自动晋级脚本必须让守卫失败"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
