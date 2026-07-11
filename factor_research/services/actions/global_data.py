"""Action jobs for global data probes."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.data.update_global_data import run_global_update

ROOT = Path(__file__).resolve().parents[2]
PROBE_LEDGER = ROOT / "reports/data/global_data_probes.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_probe(row: dict) -> None:
    PROBE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with PROBE_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_global_data_probe(dataset_id: str = "macro_daily", source_id: str = "", provider_mode: str = "") -> dict:
    result = run_global_update(
        root=ROOT,
        dataset_ids=[dataset_id] if dataset_id else [],
        provider_mode=provider_mode,
        source_id=source_id or None,
        probe=True,
    )
    row = {
        "run_at": _now(),
        "dataset_id": dataset_id,
        "source_id": source_id,
        "provider_mode": provider_mode,
        "result": result,
    }
    _append_probe(row)
    return result
