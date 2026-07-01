"""experiments read-service artifact views."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.read import experiments


def test_shadow_incubation_missing_files_returns_empty_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(experiments, "ROOT", tmp_path)

    assert experiments.shadow_incubation() == {
        "incubation": {},
        "predictions": {},
        "performance": {},
    }


def test_shadow_incubation_reads_available_json_and_ignores_bad_json(monkeypatch, tmp_path):
    monkeypatch.setattr(experiments, "ROOT", tmp_path)
    (tmp_path / "data_lake" / "agent").mkdir(parents=True)
    (tmp_path / "data_lake" / "research_signals").mkdir(parents=True)
    (tmp_path / "reports" / "islands").mkdir(parents=True)
    (tmp_path / "data_lake" / "agent" / "shadow_incubation_log.json").write_text(
        json.dumps({"active": 2}),
        encoding="utf-8",
    )
    (tmp_path / "data_lake" / "research_signals" / "ontology_predictions.json").write_text(
        "{bad json",
        encoding="utf-8",
    )
    (tmp_path / "reports" / "islands" / "shadow_ontology_performance.json").write_text(
        json.dumps({"sharpe": 0.4}),
        encoding="utf-8",
    )

    assert experiments.shadow_incubation() == {
        "incubation": {"active": 2},
        "predictions": {},
        "performance": {"sharpe": 0.4},
    }


def test_amount_timing_validation_missing_or_bad_json_returns_default(monkeypatch, tmp_path):
    monkeypatch.setattr(experiments, "ROOT", tmp_path)
    expected = {
        "latest_signal": None,
        "all_market": [],
        "ex688": [],
        "cost_sensitivity": [],
        "walk_forward": [],
    }

    assert experiments.amount_timing_validation() == expected
    (tmp_path / "reports" / "ops").mkdir(parents=True)
    (tmp_path / "reports" / "ops" / "amount_timing_validation.json").write_text(
        "{bad json",
        encoding="utf-8",
    )
    assert experiments.amount_timing_validation() == expected


def test_amount_timing_validation_reads_normal_json(monkeypatch, tmp_path):
    monkeypatch.setattr(experiments, "ROOT", tmp_path)
    (tmp_path / "reports" / "ops").mkdir(parents=True)
    payload = {"latest_signal": "2026-06-30", "all_market": [{"annual": 0.1}]}
    (tmp_path / "reports" / "ops" / "amount_timing_validation.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    assert experiments.amount_timing_validation() == payload


def test_logical_chains_reads_valid_json_files_only(monkeypatch, tmp_path):
    monkeypatch.setattr(experiments, "ROOT", tmp_path)
    logic_dir = tmp_path / "data_lake" / "research_signals" / "logic_chains"
    logic_dir.mkdir(parents=True)
    (logic_dir / "a.json").write_text(json.dumps({"id": "a"}), encoding="utf-8")
    (logic_dir / "bad.json").write_text("{bad json", encoding="utf-8")
    (logic_dir / "b.json").write_text(json.dumps({"id": "b"}), encoding="utf-8")

    assert experiments.logical_chains() == [{"id": "a"}, {"id": "b"}]


def test_industry_knowledge_graph_missing_bad_and_normal_json(monkeypatch, tmp_path):
    monkeypatch.setattr(experiments, "ROOT", tmp_path)
    default = {"nodes": [], "links": [], "meta": {"total_nodes": 0, "total_links": 0}}

    assert experiments.industry_knowledge_graph() == default
    graph_file = tmp_path / "data_lake" / "research_signals" / "industry_knowledge_graph.json"
    graph_file.parent.mkdir(parents=True)
    graph_file.write_text("{bad json", encoding="utf-8")
    assert experiments.industry_knowledge_graph() == default

    graph_file.write_text(json.dumps({"nodes": [{"id": "n"}], "links": []}), encoding="utf-8")
    assert experiments.industry_knowledge_graph() == {"nodes": [{"id": "n"}], "links": []}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
