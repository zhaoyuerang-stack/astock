"""Composite portfolio leg specification parsing."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompositeLegSpec:
    family: str
    version: str
    weight: float
    role: str = "equity_alpha"
    alias: str = ""


LEGACY_ALIASES = {
    "illiq_sc": ("illiquidity", "v3.1", "equity_alpha"),
    "lc_mom": ("hq-momentum-hedged", "v1.0", "equity_alpha"),
    "reversal": ("reversal-composite", "v1.0", "equity_alpha"),
}


def parse_composite_allocation(allocation: str) -> list[CompositeLegSpec]:
    legs: list[CompositeLegSpec] = []
    try:
        parts = [x.strip() for x in allocation.split(",") if x.strip()]
        for part in parts:
            raw_id, raw_weight = part.split(":", 1)
            weight = float(raw_weight.strip())
            leg_id = raw_id.strip()
            if leg_id in LEGACY_ALIASES:
                family, version, role = LEGACY_ALIASES[leg_id]
                legs.append(CompositeLegSpec(family, version, weight, role, alias=leg_id))
                continue
            if "/" not in leg_id:
                raise ValueError(f"unknown alias or missing family/version: {leg_id}")
            family, version = [x.strip() for x in leg_id.split("/", 1)]
            if not family or not version:
                raise ValueError(f"invalid family/version: {leg_id}")
            legs.append(CompositeLegSpec(family, version, weight))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Invalid allocation format: {allocation}. Detail: {exc}") from exc

    total = sum(x.weight for x in legs)
    if not (0.99 <= total <= 1.01):
        raise ValueError(f"Portfolio weights must sum up to 1.0, got: {total}")
    return legs


def allocation_dict(legs: list[CompositeLegSpec]) -> dict[str, float]:
    """Return legacy-compatible allocation keys for current promote_composite internals."""
    out = {}
    for leg in legs:
        key = leg.alias or f"{leg.family}/{leg.version}"
        out[key] = leg.weight
    return out
