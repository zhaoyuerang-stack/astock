"""Deterministic receipts binding registry evidence to research-ledger runs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

RECEIPT_KEY = "nine_gate_receipt"
MARGINAL_RECEIPT_KEY = "marginal_receipt"

HEX_16 = re.compile(r"^[0-9a-f]{16}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")

# Mechanical fields bound into diversifier admission receipts.
# Numbers must match admission top-level fields byte-for-byte after JSON canonicalize.
MARGINAL_BOUND_KEYS = (
    "corr_to_book",
    "residual_sharpe",
    "residual_annual",
    "beta",
    "marginal_verdict",
)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def receipt_binding(
    *, family: str, version: str, run_id: str, entry_hash: str, nine_gate_sha256: str
) -> str:
    return canonical_hash({
        "family": family,
        "version": version,
        "run_id": run_id,
        "entry_hash": entry_hash,
        "nine_gate_sha256": nine_gate_sha256,
    })


def build_nine_gate_receipt(
    family: str,
    version: str,
    nine_gate: dict,
    *,
    run_id: str,
    entry_hash: str,
) -> dict:
    """Build a receipt that the registry guard can independently recompute."""
    ng_hash = canonical_hash(nine_gate)
    return {
        "schema": 1,
        "source": "research_ledger",
        "run_id": run_id,
        "entry_hash": entry_hash,
        "nine_gate_sha256": ng_hash,
        "binding_sha256": receipt_binding(
            family=family,
            version=version,
            run_id=run_id,
            entry_hash=entry_hash,
            nine_gate_sha256=ng_hash,
        ),
    }


def marginal_metrics_payload(admission_or_metrics: dict) -> dict:
    """Extract the canonical payload whose hash is bound into a marginal receipt.

    Only keys in MARGINAL_BOUND_KEYS that are present (not None) are included so
    optional fields (beta / residual_annual / verdict) participate when supplied.
    Required fields corr_to_book and residual_sharpe must always be present.
    """
    payload: dict[str, Any] = {}
    for key in MARGINAL_BOUND_KEYS:
        if key in admission_or_metrics and admission_or_metrics[key] is not None:
            value = admission_or_metrics[key]
            # Normalize bool out — never hash True as 1.
            if isinstance(value, bool):
                continue
            if key in {"corr_to_book", "residual_sharpe", "residual_annual", "beta"}:
                payload[key] = float(value)
            else:
                payload[key] = value
    return payload


def marginal_receipt_binding(
    *, family: str, version: str, run_id: str, entry_hash: str, marginal_sha256: str
) -> str:
    return canonical_hash({
        "family": family,
        "version": version,
        "run_id": run_id,
        "entry_hash": entry_hash,
        "marginal_sha256": marginal_sha256,
        "kind": "marginal_alpha",
    })


def build_marginal_receipt(
    family: str,
    version: str,
    metrics: dict,
    *,
    run_id: str,
    entry_hash: str,
) -> dict:
    """Build a receipt binding diversifier mechanical metrics to a research run.

    ``metrics`` must include at least corr_to_book and residual_sharpe (same
    values that will be stored on admission).  The receipt is recomputable by
    the registry guard without trusting free-form rationale text.
    """
    payload = marginal_metrics_payload(metrics)
    if "corr_to_book" not in payload or "residual_sharpe" not in payload:
        raise ValueError(
            "marginal receipt requires corr_to_book and residual_sharpe in metrics"
        )
    m_hash = canonical_hash(payload)
    return {
        "schema": 1,
        "source": "research_ledger",
        "kind": "marginal_alpha",
        "run_id": run_id,
        "entry_hash": entry_hash,
        "marginal_sha256": m_hash,
        "binding_sha256": marginal_receipt_binding(
            family=family,
            version=version,
            run_id=run_id,
            entry_hash=entry_hash,
            marginal_sha256=m_hash,
        ),
    }


def verify_marginal_receipt_self_consistent(
    family: str,
    version: str,
    admission: dict,
    receipt: dict | None,
) -> list[str]:
    """Return human-readable errors if receipt is missing or does not bind metrics.

    Does **not** consult the external research ledger — that is the CI guard's job.
    Register-time only checks cryptographic self-consistency so hand-edited
    corr/residual numbers without a matching receipt cannot enter 在册.
    """
    errors: list[str] = []
    if not isinstance(receipt, dict):
        errors.append(
            f"diversifier 须提供 admission.{MARGINAL_RECEIPT_KEY} 结构化收据"
            f"（build_marginal_receipt / 绑定 research-ledger run）"
        )
        return errors

    run_id = receipt.get("run_id")
    entry_hash = receipt.get("entry_hash")
    m_hash = receipt.get("marginal_sha256")
    binding = receipt.get("binding_sha256")
    if (
        receipt.get("schema") != 1
        or receipt.get("source") != "research_ledger"
        or receipt.get("kind") != "marginal_alpha"
        or not isinstance(run_id, str)
        or HEX_16.fullmatch(run_id) is None
        or not isinstance(entry_hash, str)
        or HEX_64.fullmatch(entry_hash) is None
        or not isinstance(m_hash, str)
        or HEX_64.fullmatch(m_hash) is None
        or not isinstance(binding, str)
        or HEX_64.fullmatch(binding) is None
    ):
        errors.append(
            f"{MARGINAL_RECEIPT_KEY} 格式错误"
            f"（schema/source/kind/run_id/entry_hash/hash 须完整）"
        )
        return errors

    payload = marginal_metrics_payload(admission)
    actual = canonical_hash(payload)
    if m_hash != actual:
        errors.append(
            f"{MARGINAL_RECEIPT_KEY}.marginal_sha256 与 admission 机械字段不一致"
            f"（改 corr/residual 须重开收据，禁止拆收据改数）"
        )

    expected_binding = marginal_receipt_binding(
        family=family,
        version=version,
        run_id=run_id,
        entry_hash=entry_hash,
        marginal_sha256=m_hash,
    )
    if binding != expected_binding:
        errors.append(
            f"{MARGINAL_RECEIPT_KEY}.binding_sha256 与 family/version/run 身份不一致"
            f"（禁止把 A 策略收据贴到 B 策略）"
        )
    return errors


def diversifier_admission_with_receipt(
    family: str,
    version: str,
    *,
    rationale: str,
    corr_to_book: float,
    residual_sharpe: float,
    run_id: str,
    entry_hash: str,
    residual_annual: float | None = None,
    beta: float | None = None,
    marginal_verdict: str | None = None,
    note: str = "",
) -> dict:
    """Convenience: pack mechanical metrics + bound receipt for register()."""
    metrics: dict[str, Any] = {
        "corr_to_book": float(corr_to_book),
        "residual_sharpe": float(residual_sharpe),
    }
    if residual_annual is not None:
        metrics["residual_annual"] = float(residual_annual)
    if beta is not None:
        metrics["beta"] = float(beta)
    if marginal_verdict is not None:
        metrics["marginal_verdict"] = marginal_verdict
    receipt = build_marginal_receipt(
        family, version, metrics, run_id=run_id, entry_hash=entry_hash,
    )
    adm = {
        "track": "diversifier",
        "rationale": rationale,
        **metrics,
        MARGINAL_RECEIPT_KEY: receipt,
    }
    if note:
        adm["note"] = note
    return adm
