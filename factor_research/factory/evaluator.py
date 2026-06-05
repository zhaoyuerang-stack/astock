"""Evaluate candidate strategies through the unified BacktestEngine.

All functions in this module use ``core.engine.BacktestEngine`` as the
single backtest path.  Legacy functions (``run_candidate_returns``,
``evaluate_candidate``, ``evaluate_candidates_with_context``) have been
removed — callers should migrate to the engine-based API below.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from core.backtest import CostModel, StrategyConfig
from core.engine import BacktestConfig, BacktestEngine, PricePanel, Signal
from engine.metrics import metrics
from factors.small_cap import small_cap_factor, small_cap_timing
from strategies.small_cap import build_rebalance_weights, load_price_panels
from factory.objectives import evaluate_objectives_engine
from factory.search_space import build_factor, factor_library
from factory.timing import build_timing
from lake.schema import FUNDAMENTAL_FIELDS
from lake.load_lake import load_capital_panel, load_fundamental_panel, load_raw_close

DEFAULT_WARMUP_START = "2010-01-01"


# ---------------------------------------------------------------------------
# Context preparation
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def prepare_context(start="2018-01-01", warmup_start=DEFAULT_WARMUP_START):
    """Prepare a ``BacktestEngine`` + baseline ``BacktestResult``.

    Returns
    -------
    tuple[BacktestEngine, dict, BacktestResult]
        Engine ready to evaluate arbitrary candidates.
        Library containing factor definitions.
        Baseline small-cap-size v2.0 result for correlation comparison.
    """
    load_start = str(min(pd.Timestamp(start), pd.Timestamp(warmup_start)).date())
    close, volume, amount = load_price_panels(load_start)
    prices = PricePanel(close=close, volume=volume, amount=amount)

    codes = list(close.columns)
    fundamentals = load_fundamental_panel(close.index, codes=codes, fields=FUNDAMENTAL_FIELDS + ["industry"])
    capital = load_capital_panel(close.index, codes=codes, start=load_start)
    raw_close = load_raw_close(codes=codes, start=load_start)
    if not raw_close.empty:
        raw_close = raw_close.reindex(index=close.index, columns=close.columns)
        prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_close)

    library = factor_library(
        close, volume, amount,
        fundamentals=fundamentals,
        raw_close=raw_close,
        capital=capital,
    )

    # Baseline small-cap strategy via engine
    baseline_config = StrategyConfig(start=start)
    engine_config = BacktestConfig(
        start=start,
        cost=CostModel(
            buy_cost=baseline_config.cost.buy_cost,
            sell_cost=baseline_config.cost.sell_cost,
            financing_rate=baseline_config.cost.financing_rate,
        ),
        leverage=baseline_config.leverage,
    )
    engine = BacktestEngine(prices=prices, config=engine_config)

    baseline_factor = small_cap_factor(amount, baseline_config.size_window)
    baseline_timing, _, _ = small_cap_timing(close, amount, baseline_config.timing_ma)
    baseline_weights = build_rebalance_weights(
        baseline_factor, close,
        baseline_config.top_n, baseline_config.rebalance_days,
    )
    baseline_signal = Signal(
        weights=baseline_weights,
        timing=baseline_timing,
        family=baseline_config.family,
        version=baseline_config.version,
    )
    baseline_result = engine.run(baseline_signal)
    return engine, library, baseline_result


# ---------------------------------------------------------------------------
# Candidate evaluation
# ---------------------------------------------------------------------------

def run_candidate(candidate, engine: BacktestEngine, library, start, cost_model=None):
    """Run a single candidate through the engine.

    Parameters
    ----------
    cost_model : CostModel, optional
        Override the default cost model for this run.
    """
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
    timing = build_timing(candidate.timing, engine.prices.close, engine.prices.amount)
    scheduled = build_rebalance_weights(factor, engine.prices.close, config.top_n, config.rebalance_days)
    signal = Signal(weights=scheduled, timing=timing, family=candidate.family, version=candidate.version)

    # If cost_model differs from engine's default config, create a temporary engine
    if cost_model is not None:
        tmp_config = BacktestConfig(
            start=engine.config.start,
            cost=cost_model,
            leverage=engine.config.leverage,
            target_annual=engine.config.target_annual,
            target_maxdd=engine.config.target_maxdd,
        )
        tmp_engine = BacktestEngine(prices=engine.prices, config=tmp_config)
        return tmp_engine.run(signal)
    return engine.run(signal)


def evaluate_candidate(candidate, engine: BacktestEngine, library, baseline_result, start="2018-01-01", cost_model=None):
    """Evaluate one candidate; returns a dict with objectives."""
    result = run_candidate(candidate, engine, library, start, cost_model=cost_model)
    obj = evaluate_objectives_engine(result, baseline_result)
    return {
        "family": candidate.family,
        "version": candidate.version,
        "desc": candidate.desc,
        "config": candidate.to_dict(),
        **obj,
    }


def evaluate_candidates(candidates, start="2018-01-01"):
    """Evaluate candidates via unified ``BacktestEngine``."""
    engine, library, baseline_result = prepare_context(start)
    return [
        evaluate_candidate(c, engine, library, baseline_result, start)
        for c in candidates
    ]
