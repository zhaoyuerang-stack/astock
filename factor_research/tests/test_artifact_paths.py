"""Central runtime artifact paths."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_artifact_paths_default_to_project_root():
    from runtime.artifacts import ArtifactPaths

    project_root = Path(__file__).resolve().parents[1]
    paths = ArtifactPaths()

    assert paths.root == project_root
    assert paths.data_lake == project_root / "data_lake"
    assert paths.reports == project_root / "reports"
    assert paths.paper == project_root / "paper"
    assert paths.signals == project_root / "signals"


def test_artifact_paths_can_be_injected_for_tests(tmp_path):
    from runtime.artifacts import ArtifactPaths

    paths = ArtifactPaths(tmp_path)

    assert paths.shadow_incubation_log == tmp_path / "data_lake" / "agent" / "shadow_incubation_log.json"
    assert paths.ontology_predictions == tmp_path / "data_lake" / "research_signals" / "ontology_predictions.json"
    assert paths.amount_timing_validation == tmp_path / "reports" / "ops" / "amount_timing_validation.json"
    assert paths.logic_chains_dir == tmp_path / "data_lake" / "research_signals" / "logic_chains"
    assert paths.quality_report == tmp_path / "data_lake" / "quality_report.json"
    assert paths.data_issue_triage == tmp_path / "reports" / "data" / "data_issue_triage.json"
    assert paths.factor_health == tmp_path / "reports" / "factor_health.json"
    assert paths.decay_status == tmp_path / "reports" / "decay_status.json"
    assert paths.paper_account == tmp_path / "paper" / "account.json"
    assert paths.signal_state == tmp_path / "signals" / "state.json"
    assert paths.price_daily_dir == tmp_path / "data_lake" / "price" / "daily"
    assert paths.trade_calendar == tmp_path / "data_lake" / "meta" / "trade_calendar.parquet"
    assert paths.agent_task_log == tmp_path / "data_lake" / "agent" / "agent_tasks.jsonl"
    assert paths.config_audit_log == tmp_path / "data_lake" / "agent" / "config_audit.jsonl"
    assert paths.action_audit_log == tmp_path / "data_lake" / "agent" / "action_audit.jsonl"


def test_workspace_and_autoresearch_defaults_use_artifact_paths():
    from factory.autoresearch import repositories
    from research_ledger import workspace
    from runtime.artifacts import ArtifactPaths

    paths = ArtifactPaths()

    assert repositories.DEFAULT_ROOT == paths.autoresearch_dir
    assert repositories.DEFAULT_CANDIDATE_PATH == paths.autoresearch_candidates
    assert repositories.DEFAULT_EXPERIMENT_PATH == paths.autoresearch_experiment_log
    assert repositories.DEFAULT_REVIEW_PATH == paths.autoresearch_review_queue
    assert workspace.DEFAULT_ROOT == paths.research_workspace_dir
    assert workspace.DEFAULT_DRAFT_PATH == paths.research_workspace_drafts
    assert workspace.DEFAULT_REVIEW_PATH == paths.research_workspace_reviews


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
