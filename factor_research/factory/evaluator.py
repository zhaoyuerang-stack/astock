"""Evaluate candidate strategies through the unified core."""
from functools import lru_cache

import pandas as pd

from core.backtest import (
    CostModel,
    StrategyConfig,
    backtest_weights,
    build_rebalance_weights,
    load_price_panels,
    small_cap_factor,
    small_cap_timing,
)
from factory.objectives import evaluate_objectives
from factory.search_space import build_factor, factor_library
from factory.timing import build_timing
from lake.load_lake import FUND_FIELDS, load_fundamental_panel, load_raw_close

DEFAULT_WARMUP_START = "2010-01-01"


def _slice_from_start(ret, detail, start):
    start_ts = pd.Timestamp(start)
    ret = ret.loc[ret.index >= start_ts]
    detail = detail.loc[detail.index >= start_ts]
    return ret, detail


def run_candidate_returns(candidate, close, amount, library, start, cost_model=None):
    config = StrategyConfig(
        family=candidate.family,
        version=candidate.version,
        start=start,
        top_n=candidate.top_n,
        rebalance_days=candidate.rebalance_days,
        leverage=candidate.leverage,
        cost=cost_model or CostModel(),
    )
    factor = build_factor(candidate, library)
    timing = build_timing(candidate.timing, close, amount)
    scheduled = build_rebalance_weights(factor, close, config.top_n, config.rebalance_days)
    ret, detail = backtest_weights(close, scheduled, timing, config)
    return _slice_from_start(ret, detail, start)


def evaluate_candidate(candidate, close, amount, library, benchmark_ret, start, cost_model=None):
    ret, detail = run_candidate_returns(candidate, close, amount, library, start, cost_model=cost_model)
    obj = evaluate_objectives(ret, detail, benchmark_ret)
    return {
        "family": candidate.family,
        "version": candidate.version,
        "desc": candidate.desc,
        "config": candidate.to_dict(),
        **obj,
    }


def evaluate_candidates(candidates, start="2018-01-01"):
    close, amount, library, benchmark_ret = prepare_context(start)
    return evaluate_candidates_with_context(candidates, close, amount, library, benchmark_ret, start)


@lru_cache(maxsize=8)
def prepare_context(start="2018-01-01", warmup_start=DEFAULT_WARMUP_START):
    load_start = str(min(pd.Timestamp(start), pd.Timestamp(warmup_start)).date())
    close, volume, amount = load_price_panels(load_start)
    codes = list(close.columns)
    fundamentals = load_fundamental_panel(close.index, codes=codes, fields=FUND_FIELDS + ["industry"])
    raw_close = load_raw_close(codes=codes, start=load_start)
    if not raw_close.empty:
        raw_close = raw_close.reindex(index=close.index, columns=close.columns)
    library = factor_library(close, volume, amount, fundamentals=fundamentals, raw_close=raw_close)
    baseline_config = StrategyConfig(start=start)
    baseline_factor = small_cap_factor(amount, baseline_config.size_window)
    baseline_timing, _, _ = small_cap_timing(close, amount, baseline_config.timing_ma)
    baseline_weights = build_rebalance_weights(
        baseline_factor,
        close,
        baseline_config.top_n,
        baseline_config.rebalance_days,
    )
    benchmark_ret, _ = backtest_weights(close, baseline_weights, baseline_timing, baseline_config)
    benchmark_ret = benchmark_ret.loc[benchmark_ret.index >= pd.Timestamp(start)]
    return close, amount, library, benchmark_ret


def evaluate_candidates_with_context(candidates, close, amount, library, benchmark_ret, start="2018-01-01"):
    return [
        evaluate_candidate(c, close, amount, library, benchmark_ret, start)
        for c in candidates
    ]
