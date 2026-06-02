"""Evaluate candidate strategies through the unified core."""
from dataclasses import replace

from core.backtest import (
    StrategyConfig,
    backtest_weights,
    build_rebalance_weights,
    load_price_panels,
    run_small_cap_strategy,
    small_cap_timing,
)
from factory.objectives import evaluate_objectives
from factory.search_space import build_factor, factor_library


def evaluate_candidate(candidate, close, amount, library, benchmark_ret, start):
    config = StrategyConfig(
        family=candidate.family,
        version=candidate.version,
        start=start,
        top_n=candidate.top_n,
        rebalance_days=candidate.rebalance_days,
        leverage=candidate.leverage,
    )
    factor = build_factor(candidate, library)
    timing, _, _ = small_cap_timing(close, amount, config.timing_ma)
    scheduled = build_rebalance_weights(factor, close, config.top_n, config.rebalance_days)
    ret, detail = backtest_weights(close, scheduled, timing, config)
    obj = evaluate_objectives(ret, detail, benchmark_ret)
    return {
        "family": candidate.family,
        "version": candidate.version,
        "desc": candidate.desc,
        "config": candidate.to_dict(),
        **obj,
    }


def evaluate_candidates(candidates, start="2018-01-01"):
    close, volume, amount = load_price_panels(start)
    library = factor_library(close, volume, amount)
    baseline = run_small_cap_strategy(StrategyConfig(start=start))
    benchmark_ret = baseline["returns"]
    return [
        evaluate_candidate(c, close, amount, library, benchmark_ret, start)
        for c in candidates
    ]
