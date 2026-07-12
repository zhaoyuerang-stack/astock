"""Dry-run-first migration of strategy-family risk metadata.

This historical helper used to rewrite ``strategy_versions.json`` directly.
That bypassed the registry invariants and could target the main checkout even
when invoked from another worktree.  The migration now discovers the current
checkout from ``__file__`` and delegates every write to
``strategy_registry.register_family``.

Running without arguments is read-only.  Use ``--apply`` only after reviewing
the printed diff.  The operation is idempotent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import strategy_registry


UPGRADES = {
    "small-cap-size": {
        "style_betas": {"size": 0.85, "volatility": 0.20, "value": -0.10},
        "capacity_m": 20.0,
        "failure_boundaries": {"max_drawdown": -0.35, "max_drawdown_days": 180},
    },
    "large-cap-growth-hedged": {
        "style_betas": {"size": -0.50, "growth": 0.60, "value": -0.40},
        "capacity_m": 150.0,
        "failure_boundaries": {"max_drawdown": -0.15, "max_drawdown_days": 120},
    },
    "industry-neglect-rotation": {
        "style_betas": {"size": 0.15, "value": 0.30, "crowdness": -0.60},
        "capacity_m": 80.0,
        "failure_boundaries": {"max_drawdown": -0.30, "max_drawdown_days": 150},
    },
    "hq-momentum-hedged": {
        "style_betas": {"momentum": 0.55, "quality": 0.45, "size": 0.10},
        "capacity_m": 100.0,
        "failure_boundaries": {"max_drawdown": -0.22, "max_drawdown_days": 120},
    },
    "d-le-sc-hedged": {
        "style_betas": {"size": -0.08, "momentum": -0.12, "idiosyncratic": 0.90},
        "capacity_m": 30.0,
        "failure_boundaries": {"max_drawdown": -0.30, "max_drawdown_days": 180},
    },
    "illiquidity": {
        "style_betas": {"size": 0.75, "illiquidity": 0.80, "volatility": 0.10},
        "capacity_m": 15.0,
        "failure_boundaries": {"max_drawdown": -0.30, "max_drawdown_days": 180},
    },
    "size-earnings": {
        "style_betas": {"size": 0.65, "quality": 0.40, "volatility": 0.15},
        "capacity_m": 25.0,
        "failure_boundaries": {"max_drawdown": -0.25, "max_drawdown_days": 150},
    },
    "size-low-vol": {
        "style_betas": {"size": 0.70, "volatility": -0.40, "value": 0.05},
        "capacity_m": 30.0,
        "failure_boundaries": {"max_drawdown": -0.25, "max_drawdown_days": 150},
    },
}


def build_plan() -> list[dict]:
    """Return a read-only migration plan from the current registry snapshot."""

    families = {
        family["id"]: family
        for family in strategy_registry._load().get("families", [])
    }
    plan = []
    for family_id, desired in UPGRADES.items():
        family = families.get(family_id)
        if family is None:
            plan.append({"family": family_id, "missing": True, "changed": False})
            continue

        before = {
            "style_betas": family.get("style_betas") or {},
            "capacity_m": float(family.get("capacity_m") or 0.0),
            "failure_boundaries": family.get("failure_boundaries") or {},
        }
        plan.append(
            {
                "family": family_id,
                "missing": False,
                "changed": before != desired,
                "before": before,
                "after": desired,
            }
        )
    return plan


def apply_plan(plan: list[dict]) -> list[str]:
    """Apply changed rows exclusively through the canonical registry writer."""

    applied = []
    for item in plan:
        if item.get("missing") or not item.get("changed"):
            continue
        # Refresh immediately before each canonical write.  A reviewed plan may
        # sit open while another agent edits family metadata; do not replay the
        # stale preview snapshot over those edits.
        family = next(
            (
                row
                for row in strategy_registry._load().get("families", [])
                if row.get("id") == item["family"]
            ),
            None,
        )
        if family is None:
            continue
        desired = item["after"]
        current = {
            "style_betas": family.get("style_betas") or {},
            "capacity_m": float(family.get("capacity_m") or 0.0),
            "failure_boundaries": family.get("failure_boundaries") or {},
        }
        if current == desired:
            continue
        strategy_registry.register_family(
            id=family["id"],
            name=family.get("name", ""),
            hypothesis=family.get("hypothesis", ""),
            regime=family.get("regime", ""),
            decay_signal=family.get("decay_signal", ""),
            status=family.get("status", "active"),
            style_betas=desired["style_betas"],
            capacity_m=desired["capacity_m"],
            failure_boundaries=desired["failure_boundaries"],
        )
        applied.append(family["id"])
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply the reviewed plan through strategy_registry.register_family",
    )
    args = parser.parse_args(argv)

    plan = build_plan()
    for item in plan:
        if item["missing"]:
            print(f"SKIP missing family: {item['family']}")
        elif item["changed"]:
            print(f"CHANGE {item['family']}: {item['before']} -> {item['after']}")
        else:
            print(f"OK unchanged: {item['family']}")

    if not args.apply:
        print("DRY RUN: no registry writes. Re-run with --apply after review.")
        return 0

    applied = apply_plan(plan)
    print(f"Applied through canonical registry API: {len(applied)} families")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
