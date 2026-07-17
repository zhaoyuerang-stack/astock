"""Controlled L0 signal probe wrapper (ADR-037).

Produces reports under reports/research/ only. Never writes registry.
Not alpha admission (R-LLM-001 / R-WF-001).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app_config.settings import get_settings

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports" / "research"


def _holdout_boundary() -> str:
    try:
        s = get_settings()
        # holdout may live under settings; fail-closed to a conservative default
        hb = getattr(getattr(s, "research", None), "holdout_boundary", None) or getattr(
            getattr(s, "holdout", None), "boundary", None
        )
        if hb:
            return str(hb)[:10]
    except Exception:
        pass
    # ADR-021 style default used across repo when unset
    return "2025-01-01"


def run_signal_probe(
    *,
    factor_name: str,
    idea: str = "",
    start: str = "2018-01-01",
    cutoff: str = "2022-12-31",
    end: str | None = None,
) -> dict[str, Any]:
    """Lightweight L0 probe entry for Agent.

    For unknown factors, returns a blocked envelope payload without inventing IC.
    For registered factor names, records a probe job receipt (full heavy probe
    remains scripts/research/signal_source_probe.py for human ops).
    """
    boundary = _holdout_boundary()
    end = end or "2024-12-31"
    if str(end) >= boundary:
        raise ValueError(
            f"probe end={end} must be < holdout boundary={boundary} (ADR-021)"
        )
    if str(cutoff) >= boundary:
        raise ValueError(f"probe cutoff={cutoff} must be < holdout boundary={boundary}")

    from factors.registry import FACTOR_REGISTRY, discover

    discover()
    registered = factor_name in FACTOR_REGISTRY

    receipt = {
        "factor_name": factor_name,
        "idea": idea,
        "start": start,
        "cutoff": cutoff,
        "end": end,
        "holdout_boundary": boundary,
        "registered": registered,
        "status": "blocked_unregistered" if not registered else "queued_l0_receipt",
        "can_claim_valid": False,
        "evidence_tier": "l0_probe" if registered else "precheck",
        "note": (
            "Unregistered factor: run data_gap_audit / onboarding before probe."
            if not registered
            else (
                "L0 receipt only — full IC/orthogonality probe via "
                "scripts/research/signal_source_probe.py; this action does not admit alpha."
            )
        ),
        "formal_path_allowed": "reports/research/",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in factor_name)[:60]
    out = REPORTS / f"agent_l0_probe_receipt_{safe}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    receipt["report_path"] = str(out.relative_to(ROOT))
    return receipt
