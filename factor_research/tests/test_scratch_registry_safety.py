"""Regression coverage for version-controlled scratch registry helpers."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import strategy_registry


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRATCH = ROOT / "scratch"


def _load_script(name: str):
    path = SCRATCH / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"scratch_test_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seed_registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "families": [
                    {
                        "id": "d-le-sc-hedged",
                        "name": "D-LE-SC",
                        "hypothesis": "preserve hypothesis",
                        "regime": "preserve regime",
                        "decay_signal": "preserve decay signal",
                        "status": "paused",
                        "versions": [{"version": "v1.0", "status": "参考"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_migrate_ledger_dry_run_is_read_only(tmp_path, monkeypatch, capsys):
    migration = _load_script("migrate_ledger")
    registry = tmp_path / "strategy_versions.json"
    _seed_registry(registry)
    monkeypatch.setattr(strategy_registry, "REGISTRY", registry)
    before = registry.read_bytes()

    assert migration.main([]) == 0

    assert registry.read_bytes() == before
    assert "DRY RUN: no registry writes" in capsys.readouterr().out


def test_migrate_ledger_apply_uses_canonical_api_and_is_idempotent(
    tmp_path, monkeypatch
):
    migration = _load_script("migrate_ledger")
    registry = tmp_path / "strategy_versions.json"
    _seed_registry(registry)
    monkeypatch.setattr(strategy_registry, "REGISTRY", registry)

    calls = []
    canonical_register_family = strategy_registry.register_family

    def recording_register_family(*args, **kwargs):
        calls.append((args, kwargs))
        return canonical_register_family(*args, **kwargs)

    monkeypatch.setattr(
        migration.strategy_registry,
        "register_family",
        recording_register_family,
    )

    plan = migration.build_plan()
    assert migration.apply_plan(plan) == ["d-le-sc-hedged"]
    assert len(calls) == 1

    family = json.loads(registry.read_text(encoding="utf-8"))["families"][0]
    assert family["versions"] == [{"version": "v1.0", "status": "参考"}]
    assert family["hypothesis"] == "preserve hypothesis"
    assert family["regime"] == "preserve regime"
    assert family["decay_signal"] == "preserve decay signal"
    assert family["status"] == "paused"
    assert family["style_betas"] == migration.UPGRADES["d-le-sc-hedged"]["style_betas"]
    assert family["capacity_m"] == 30.0
    assert family["failure_boundaries"] == {
        "max_drawdown": -0.30,
        "max_drawdown_days": 180,
    }

    assert not next(
        item
        for item in migration.build_plan()
        if item["family"] == "d-le-sc-hedged"
    )["changed"]


def test_retired_register_v3_is_explicitly_blocked(capsys):
    retired = _load_script("register_v3")

    assert retired.main() == 2
    assert "BLOCKED" in capsys.readouterr().out


def test_scratch_scripts_do_not_pin_a_developer_checkout():
    python_files = sorted(SCRATCH.rglob("*.py"))
    assert python_files

    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in python_files
        if "/Users/" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_scratch_scripts_cannot_call_private_registry_save():
    offenders = []
    for path in sorted(SCRATCH.rglob("*.py")):
        rel = str(path.relative_to(REPO_ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else ""
            )
            if name == "_save":
                offenders.append(f"{rel}:L{node.lineno}")
    assert offenders == []
