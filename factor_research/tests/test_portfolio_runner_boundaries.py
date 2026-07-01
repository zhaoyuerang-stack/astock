"""Portfolio runner module boundary tests."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_strategy_runners_reexports_split_modules():
    from portfolio import deployment_runner, research_catalog, strategy_runners

    assert strategy_runners.RESEARCH_STRATEGY_CATALOG is research_catalog.RESEARCH_STRATEGY_CATALOG
    assert strategy_runners.RESEARCH_STRATEGIES is research_catalog.RESEARCH_STRATEGIES
    assert strategy_runners.run_all_live is research_catalog.run_all_live
    assert strategy_runners.run_active is deployment_runner.run_active
    assert strategy_runners.active_strategies is deployment_runner.active_strategies
    assert strategy_runners.defensive_strategies is deployment_runner.defensive_strategies


def test_active_strategies_prefers_deployment_manifest(monkeypatch):
    from portfolio import deployment_runner

    dep = SimpleNamespace(
        legs=[
            SimpleNamespace(family="fam-a", version="v1", role="equity_alpha"),
            SimpleNamespace(family="fam-b", version="v2", role="defensive"),
        ]
    )
    monkeypatch.setattr(deployment_runner, "load_active_deployment", lambda: dep)

    assert deployment_runner.active_strategies() == ["fam-a.v1", "fam-b.v2"]
    assert deployment_runner.defensive_strategies() == {"fam-b.v2"}


def test_active_strategies_falls_back_to_research_catalog(monkeypatch):
    from portfolio import deployment_runner, research_catalog

    def not_ready():
        raise deployment_runner.DeploymentNotReady("paused")

    monkeypatch.setattr(deployment_runner, "load_active_deployment", not_ready)
    monkeypatch.setattr(
        research_catalog,
        "RESEARCH_STRATEGY_CATALOG",
        {
            "active-a.v1": {"status": "ACTIVE", "fn": object()},
            "shadow-a.v1": {"status": "SHADOW", "fn": object()},
            "active-def.v1": {"status": "ACTIVE", "role": "defensive", "fn": object()},
        },
    )

    assert deployment_runner.active_strategies() == ["active-a.v1", "active-def.v1"]
    assert deployment_runner.defensive_strategies() == {"active-def.v1"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
