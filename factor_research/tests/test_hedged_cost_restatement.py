from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import strategy_registry
from scripts.repair import restate_hedged_execution_costs as repair


def _registry_payload() -> dict:
    families = []
    by_family: dict[str, list[str]] = {}
    for family, version in repair.EXPECTED_TARGETS:
        by_family.setdefault(family, []).append(version)
    for family, versions in sorted(by_family.items()):
        families.append(
            {
                "id": family,
                "status": "active",
                "versions": [
                    {
                        "version": version,
                        "status": "退役" if not version.endswith("full") else "参考",
                        "config": {"cost": {"hedge_cost_annual": 0.015}},
                        "metrics": {
                            "annual": 0.10,
                            "maxdd": -0.10,
                            "sharpe": 1.0,
                            "calmar": 1.0,
                            "hit": False,
                        },
                        "notes": "旧免成本正收益叙述",
                        "admission": {
                            "track": "diversifier",
                            "rationale": "旧组合边际",
                        },
                        "nine_gate": {"dsr_p": 0.9},
                        "evidence": {},
                    }
                    for version in sorted(versions)
                ],
            }
        )
    return {"families": families}


@pytest.fixture
def temp_registry(tmp_path, monkeypatch):
    path = tmp_path / "strategy_versions.json"
    path.write_text(json.dumps(_registry_payload(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(strategy_registry, "REGISTRY", path)
    return path


def _fake_runner(_name: str, _config: dict) -> dict:
    index = pd.bdate_range("2010-01-01", "2024-12-31")
    returns = pd.Series(-0.0001, index=index, dtype=float)
    cost = pd.Series(0.0002, index=index, dtype=float)
    return {
        "returns": returns,
        "engine_result": SimpleNamespace(cost=cost),
    }


def _plan(monkeypatch) -> list[dict]:
    monkeypatch.setattr(repair, "_data_vintage", lambda: {"fingerprint": "test-data"})
    monkeypatch.setattr(repair, "_source_hashes", lambda _runner: {"source.py": "a" * 64})
    return repair.build_restatement_plan(
        runner=_fake_runner,
        run_at="2026-07-10T12:00:00+00:00",
    )


def test_dry_run_plan_covers_all_six_without_writing(temp_registry, monkeypatch):
    before = temp_registry.read_bytes()
    plan = _plan(monkeypatch)

    assert {(row["family"], row["version"]) for row in plan} == repair.EXPECTED_TARGETS
    assert len(plan) == 6
    assert all(row["audit"]["sample_end"] == "2024-12-31" for row in plan)
    assert all(row["audit"]["long_leg_cost_total"] > 0 for row in plan)
    assert all(len(row["audit"]["source_bundle_digest"]) == 64 for row in plan)
    assert temp_registry.read_bytes() == before


def test_apply_uses_narrow_api_preserves_status_and_nine_gate(temp_registry, monkeypatch, tmp_path):
    before = strategy_registry._load()
    old_records = {
        (family["id"], version["version"]): deepcopy(version)
        for family in before["families"]
        for version in family["versions"]
    }
    plan = _plan(monkeypatch)
    returns_root = tmp_path / "version_returns"
    repair.apply_restatement_plan(plan, returns_root=returns_root)
    after = strategy_registry._load()

    for family in after["families"]:
        for version in family["versions"]:
            identity = (family["id"], version["version"])
            old = old_records[identity]
            assert version["status"] == old["status"]
            assert version["nine_gate"] == old["nine_gate"]
            assert version["metrics"]["annual"] < 0
            assert version["metrics"]["hit"] is False
            assert version["config"]["cost"]["buy_cost"] == 0.00225
            assert version["config"]["cost"]["sell_cost"] == 0.00275
            assert version["admission"]["evidence_status"] == "INVALIDATED_BY_COST_RESTATEMENT"
            assert "作废" in version["admission"]["note"]
            assert "靠组合层增量入册" not in version["admission"]["note"]
            rows = version["evidence"]["execution_cost_restatements"]
            assert len(rows) == 1
            assert rows[0]["prior_record"]["notes"] == "旧免成本正收益叙述"
            cache = returns_root / f"{family['id']}__{version['version']}.csv"
            assert cache.is_file()
            cached = pd.read_csv(cache, index_col=0, parse_dates=True)["ret"]
            expected = next(
                row["returns"] for row in plan
                if (row["family"], row["version"]) == identity
            )
            pd.testing.assert_series_equal(cached, expected, check_names=False, check_freq=False)


def test_reapplying_same_evidence_is_idempotent(temp_registry, monkeypatch, tmp_path):
    plan = _plan(monkeypatch)
    returns_root = tmp_path / "version_returns"
    repair.apply_restatement_plan(plan, returns_root=returns_root)
    first = temp_registry.read_bytes()

    second_plan = _plan(monkeypatch)
    assert all(row["already_applied"] for row in second_plan)
    repair.apply_restatement_plan(second_plan, returns_root=returns_root)

    assert temp_registry.read_bytes() == first


def test_registry_api_rejects_noncanonical_cost_without_mutation(temp_registry):
    before = temp_registry.read_bytes()
    audit = {
        "audit_id": "bad-cost",
        "rule": "R-COST-001 / ADR-032",
        "run_at": "2026-07-10T12:00:00+00:00",
        "runner": "strategies.large_cap",
        "sample_start": "2023-01-01",
        "sample_end": "2024-12-31",
        "return_digest": "a" * 64,
        "source_hashes": {"source.py": "b" * 64},
    }
    with pytest.raises(ValueError, match="canonical CostModel"):
        strategy_registry.restate_execution_costs(
            "large-cap-growth-hedged",
            "v1.0",
            metrics={
                "annual": -0.1,
                "maxdd": -0.2,
                "sharpe": -0.3,
                "calmar": -0.5,
                "n": 400,
            },
            cost_model={
                "buy_cost": 0.0,
                "sell_cost": 0.0,
                "financing_rate": 0.0,
            },
            audit=audit,
            notes="truthful",
        )
    assert temp_registry.read_bytes() == before


def test_plan_refuses_runner_with_zero_long_leg_cost(temp_registry, monkeypatch):
    monkeypatch.setattr(repair, "_data_vintage", lambda: {"fingerprint": "test-data"})
    monkeypatch.setattr(repair, "_source_hashes", lambda _runner: {"source.py": "a" * 64})

    def zero_cost_runner(name, config):
        result = _fake_runner(name, config)
        result["engine_result"].cost[:] = 0.0
        return result

    with pytest.raises(RuntimeError, match="charged no long-leg transaction cost"):
        repair.build_restatement_plan(runner=zero_cost_runner)
