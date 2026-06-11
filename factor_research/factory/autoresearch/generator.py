"""Deterministic seed candidate generation for AutoResearch Lite."""
from __future__ import annotations

from collections.abc import Iterator

from .models import Candidate
from .validator import validate_candidate_ast


_SEEDS = [
    ("momentum", {"window": 20}, "volume_ratio", {"window": 5}),
    ("momentum", {"window": 60}, "volatility", {"window": 20}),
    ("momentum", {"window": 120}, "illiquidity", {"window": 20}),
    ("volume_ratio", {"window": 10}, "volatility", {"window": 60}),
    ("illiquidity", {"window": 40}, "momentum", {"window": 20}),
    ("roe", {}, "momentum", {"window": 60}),
    ("net_profit_yoy", {}, "volume_ratio", {"window": 20}),
    ("revenue_yoy", {}, "momentum", {"window": 120}),
    ("bp_proxy", {}, "volatility", {"window": 60}),
    ("ep_proxy", {}, "illiquidity", {"window": 20}),
    ("roe", {}, "bp_proxy", {}),
    ("net_profit_yoy", {}, "revenue_yoy", {}),
]


def _ast_for(seed: tuple, weight: float) -> dict:
    left_factor, left_params, right_factor, right_params = seed
    return {
        "type": "linear_combo",
        "terms": [
            {
                "factor": left_factor,
                "params": left_params,
                "transforms": ["mad_clip", "zscore", "rank"],
                "weight": weight,
            },
            {
                "factor": right_factor,
                "params": right_params,
                "transforms": ["mad_clip", "zscore", "rank"],
                "weight": round(1.0 - weight, 2),
            },
        ],
        "direction": "positive",
        "thesis": {
            "mechanism": f"{left_factor} 与 {right_factor} 的互补信号组合,用于受控自动研究初筛。",
            "citation": "autoresearch seed generator",
        },
    }


def generate_seed_candidates(limit: int = 10) -> Iterator[Candidate]:
    """Yield unique, validated low-complexity seed candidates."""
    seen: set[str] = set()
    weights = [0.7, 0.6, 0.5]
    for seed in _SEEDS:
        for weight in weights:
            candidate = validate_candidate_ast(_ast_for(seed, weight))
            if candidate.fingerprint in seen:
                continue
            seen.add(candidate.fingerprint)
            yield candidate
            if len(seen) >= limit:
                return
