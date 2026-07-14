from __future__ import annotations

from pathlib import Path

import conftest
import pandas as pd
import pytest


def test_profile_is_stub_when_any_required_file_is_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conftest, "ROOT", tmp_path)
    assert conftest.data_lake_profile() == "STUB"
    assert conftest.missing_required_data_lake_files()


def test_profile_is_full_when_every_required_file_exists(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(conftest, "ROOT", tmp_path)
    for relative in conftest.REQUIRED_LAKE_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    assert conftest.data_lake_profile() == "FULL"
    assert conftest.missing_required_data_lake_files() == ()


def test_canonical_runner_executes_full_pytest_suite():
    runner = Path(__file__).parents[1] / "scripts" / "test_all.sh"
    text = runner.read_text(encoding="utf-8")
    assert "python3 -m pytest -q" in text
    assert "tests/test_" not in text


def test_pytest_runtime_blocks_indirect_writes_to_real_lake():
    target = conftest.ROOT / "data_lake" / "_pytest_must_not_create.parquet"
    with pytest.raises(RuntimeError, match="canonical data_lake forbidden"):
        pd.DataFrame({"x": [1]}).to_parquet(target)
    assert not target.exists()
    with pytest.raises(RuntimeError, match="canonical data_lake forbidden"):
        target.with_suffix(".txt").open("w")


def test_pytest_runtime_allows_temp_lake_writes(tmp_path: Path):
    target = tmp_path / "data_lake" / "fixture.parquet"
    target.parent.mkdir()
    pd.DataFrame({"x": [1]}).to_parquet(target)
    assert target.is_file()


def test_pytest_runtime_isolates_research_feedback_files(isolated_runtime_files):
    from knowledge import graph as knowledge_graph
    from workflow import phase1_synthetic, phase4_register

    lessons = isolated_runtime_files["pending_lessons"]
    store = isolated_runtime_files["knowledge_store"]
    assert phase1_synthetic.LESSONS_DIR == lessons
    assert phase4_register.LESSONS_DIR == lessons
    assert Path(knowledge_graph.DEFAULT_STORE) == store

    summary = knowledge_graph.sync_pending_lessons_to_graph()
    assert Path(summary["store_path"]) == store
