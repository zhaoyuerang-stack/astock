"""Deterministic seed candidate generation for AutoResearch Lite."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

from .models import Candidate
from .validator import validate_candidate_ast


_SEEDS = [
    # 股东户数正交族置顶(probe 实测最强正交源:原始 ICIR 0.57、OOS 留存 159%、残差去 size/流动后
    # 87% OOS 不塌)。户数减少=筹码集中=机构吸筹。集中度 × 趋势 / 质量。
    ("holder_count_chg", {"window": 60}, "momentum", {"window": 20}),
    ("holder_count_chg", {"window": 60}, "roe", {}),
    # 北向资金正交族置顶(打破小盘坍缩):islands 以小 limit 采种,置顶保证 smart-money
    # 正交维度必进搜索初始种群。smart-money × 趋势 / 质量。
    ("northbound_accumulation", {"window": 20}, "momentum", {"window": 20}),
    ("northbound_accumulation", {"window": 20}, "roe", {}),
    ("momentum", {"window": 20}, "volume_ratio", {"window": 5}),
    ("alpha_003", {}, "bp_proxy", {}),
    ("momentum", {"window": 60}, "volatility", {"window": 20}),
    ("alpha_055", {}, "roe", {}),
    ("momentum", {"window": 120}, "illiquidity", {"window": 20}),
    ("alpha_013", {}, "volatility", {"window": 60}),
    ("volume_ratio", {"window": 10}, "volatility", {"window": 60}),
    ("alpha_050", {}, "ep_proxy", {}),
    ("illiquidity", {"window": 40}, "momentum", {"window": 20}),
    ("alpha_044", {}, "net_profit_yoy", {}),
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
            # ADR-022 种子溯源:确定性种子源自教科书因子(generator._SEEDS),无金库语义。
            yield replace(candidate, provenance={
                "origin": "deterministic_seed",
                "catalog": "factory.autoresearch.generator._SEEDS",
                "pair": f"{seed[0]}×{seed[2]}",
            })
            if len(seen) >= limit:
                return
