"""Task 16: 测试发现完整性守卫的自测。"""
from pathlib import Path

import pytest

from scripts.ci import check_test_discovery as guard


def test_discovers_pytest_style_files():
    files = guard.discover_test_files()
    # 本整改新增的测试必须在发现集中(否则会被静默排除)
    assert "tests/test_strategy_spec.py" in files
    assert "tests/test_nine_gate_policy.py" in files
    assert "tests/test_deployment_manifest.py" in files


def test_script_only_test_file_is_not_silently_exempted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    script = tests_dir / "test_script_only.py"
    script.write_text(
        "if __name__ == '__main__':\n    raise SystemExit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(guard, "ROOT", tmp_path)

    assert guard.discover_test_files() == {"tests/test_script_only.py"}
    monkeypatch.setattr(guard, "collected_test_files", lambda: (set(), ""))
    assert guard.main() == 1


def test_guard_passes_on_current_repo():
    # 全仓 pytest 风格测试都应可被收集(无静默排除)
    assert guard.main() == 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
