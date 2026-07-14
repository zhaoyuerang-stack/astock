"""Deterministic pytest environment profile for shared worktrees."""
from __future__ import annotations

import builtins
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent
REQUIRED_LAKE_FILES = (
    "data_lake/price/daily_all.parquet",
    "data_lake/price/daily_raw_all.parquet",
    "data_lake/meta/trade_calendar.parquet",
    "data_lake/meta/codes.parquet",
    "data_lake/financials/income_all.parquet",
    "data_lake/financials/fina_indicator_all.parquet",
    "data_lake/capital/margin_all.parquet",
    # Extra files used by the stock-profile and holder PIT integration tests.
    # Keeping them in the profile prevents a partial lake from being reported
    # as FULL only to fail later in an unclassified way.
    "data_lake/holder/holdernumber_all.parquet",
    "data_lake/price/daily/600519.parquet",
    "data_lake/price/daily/300124.parquet",
    "data_lake/daily_basic/daily_basic_all.parquet",
)


def missing_lake_files() -> tuple[str, ...]:
    return tuple(rel for rel in REQUIRED_LAKE_FILES if not (ROOT / rel).is_file())


def missing_required_data_lake_files() -> tuple[str, ...]:
    """Public profile helper shared by pytest and the canonical CI guard."""
    return missing_lake_files()


def data_lake_profile() -> str:
    return "FULL" if not missing_lake_files() else "STUB"


def pytest_report_header(config):
    missing = missing_lake_files()
    return f"factor_research data profile: {data_lake_profile()} (missing={len(missing)})"


def pytest_collection_modifyitems(config, items):
    missing = missing_lake_files()
    if not missing:
        return
    reason = (
        "data_lake profile=STUB; missing canonical files: "
        + ", ".join(missing[:3])
        + (f" (+{len(missing) - 3} more)" if len(missing) > 3 else "")
    )
    marker = pytest.mark.skip(reason=reason)
    for item in items:
        if item.get_closest_marker("requires_data_lake") is not None:
            item.add_marker(marker)


@pytest.fixture(autouse=True)
def isolated_runtime_files(monkeypatch, tmp_path):
    """Keep mutable agent runtime state inside each test's temp directory."""
    from knowledge import graph as knowledge_graph
    from services.actions import action_guard
    from services.agent import llm_adapter, planner
    from workflow import phase1_synthetic, phase4_register

    runtime_root = tmp_path / "agent_runtime"
    paths = {
        "task_log": runtime_root / "agent_tasks.jsonl",
        "action_token": runtime_root / "action_token",
        "action_audit": runtime_root / "action_audit.jsonl",
        "llm_config": runtime_root / "llm_config.json",
        "pending_lessons": runtime_root / "pending_lessons",
        "knowledge_store": runtime_root / "findings.json",
    }
    paths["pending_lessons"].mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(planner, "_TASK_LOG", paths["task_log"])
    monkeypatch.setattr(action_guard, "ACTION_TOKEN_FILE", paths["action_token"])
    monkeypatch.setattr(action_guard, "ACTION_AUDIT_FILE", paths["action_audit"])
    monkeypatch.setattr(llm_adapter, "_RUNTIME", paths["llm_config"])
    monkeypatch.setattr(phase1_synthetic, "LESSONS_DIR", paths["pending_lessons"])
    monkeypatch.setattr(phase4_register, "LESSONS_DIR", paths["pending_lessons"])
    original_sync = knowledge_graph.sync_pending_lessons_to_graph

    def isolated_sync(pending_dir=None, store_path=None):
        return original_sync(
            pending_dir=pending_dir or paths["pending_lessons"],
            store_path=store_path or paths["knowledge_store"],
        )

    monkeypatch.setattr(knowledge_graph, "DEFAULT_STORE", str(paths["knowledge_store"]))
    monkeypatch.setattr(knowledge_graph, "sync_pending_lessons_to_graph", isolated_sync)
    return paths


def _is_canonical_lake_path(value) -> bool:
    if not isinstance(value, (str, bytes, Path)):
        return False
    try:
        path = Path(value).expanduser().resolve()
        path.relative_to((ROOT / "data_lake").resolve())
        return True
    except (OSError, TypeError, ValueError):
        return False


@pytest.fixture(autouse=True)
def block_writes_to_canonical_lake(monkeypatch):
    """Tests may read the real lake, but every write must target a temp root."""
    original_open = builtins.open
    original_path_open = Path.open
    original_write_text = Path.write_text
    original_write_bytes = Path.write_bytes

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in str(mode) for flag in ("w", "a", "x", "+")) and _is_canonical_lake_path(file):
            raise RuntimeError(f"pytest write to canonical data_lake forbidden: {file}")
        return original_open(file, mode, *args, **kwargs)

    def guarded_write_text(path, *args, **kwargs):
        if _is_canonical_lake_path(path):
            raise RuntimeError(f"pytest write to canonical data_lake forbidden: {path}")
        return original_write_text(path, *args, **kwargs)

    def guarded_path_open(path, mode="r", *args, **kwargs):
        if any(flag in str(mode) for flag in ("w", "a", "x", "+")) and _is_canonical_lake_path(path):
            raise RuntimeError(f"pytest write to canonical data_lake forbidden: {path}")
        return original_path_open(path, mode, *args, **kwargs)

    def guarded_write_bytes(path, *args, **kwargs):
        if _is_canonical_lake_path(path):
            raise RuntimeError(f"pytest write to canonical data_lake forbidden: {path}")
        return original_write_bytes(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(Path, "open", guarded_path_open)
    monkeypatch.setattr(Path, "write_text", guarded_write_text)
    monkeypatch.setattr(Path, "write_bytes", guarded_write_bytes)

    for owner in (pd.DataFrame, pd.Series):
        for method_name in ("to_parquet", "to_csv", "to_feather", "to_pickle"):
            original = getattr(owner, method_name, None)
            if original is None:
                continue

            def guarded_writer(obj, path, *args, _original=original, **kwargs):
                if _is_canonical_lake_path(path):
                    raise RuntimeError(f"pytest write to canonical data_lake forbidden: {path}")
                return _original(obj, path, *args, **kwargs)

            monkeypatch.setattr(owner, method_name, guarded_writer)
