"""Composite leg weight runners used by workflow promotion."""
from __future__ import annotations

from typing import Callable

import pandas as pd

from core.engine import BacktestConfig, BacktestEngine, CostModel, PricePanel, Signal
from core.risk.dual_valve import apply_dual_valve_gating
from factors.autoresearch_dsl import compute_dsl_factor

CompositeWeightRunner = Callable[
    [PricePanel, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
    tuple[pd.DataFrame, pd.DataFrame],
]

AST_REVERSAL = {
    "type": "linear_combo",
    "terms": [
        {"factor": "momentum", "params": {"window": 60}, "transforms": ["mad_clip", "zscore", "rank"], "weight": 0.5},
        {"factor": "revenue_yoy", "params": {}, "transforms": ["mad_clip", "zscore", "rank"], "weight": 0.37},
    ],
    "direction": "negative",
    "execution": {"portfolio_size": 25, "rebalance_freq": "20D"},
}


def build_illiquidity_v31_weights(
    prices: PricePanel,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    amount: pd.DataFrame,
    total_mv: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sc_universe = total_mv.rank(axis=1, ascending=True, pct=False) <= 800
    amihud = (close.pct_change().abs() / amount).rolling(20).mean()
    amihud_sc = amihud.where(sc_universe)

    signal = Signal(
        factor=amihud_sc.rank(axis=1, pct=True),
        top_n=25,
        direction=1,
        rebalance_freq="20D",
        family="illiquidity",
        version="v3.1",
    )
    engine = BacktestEngine(prices, BacktestConfig(leverage=1.0, cost=CostModel(), start="2010-01-01"))
    base = engine.run(signal)

    nav = (1 + base.returns).cumprod()
    timing = pd.Series(0.0, index=base.returns.index)
    timing[nav > nav.rolling(16).mean()] = 1.0
    timing = timing.reindex(close.index).ffill().fillna(0.0)
    weights = signal._resolve_weights(prices).reindex(close.index).ffill().fillna(0.0)
    return weights.mul(timing, axis=0), weights.mul(timing.shift(1).fillna(0.0), axis=0)


def build_hq_momentum_hedged_v10_weights(
    prices: PricePanel,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    amount: pd.DataFrame,
    total_mv: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    lc_universe = total_mv.rank(axis=1, ascending=False, pct=False) <= 200
    momentum = close.pct_change(120).where(lc_universe)

    signal = Signal(
        factor=momentum.rank(axis=1, pct=True),
        top_n=25,
        direction=1,
        rebalance_freq="20D",
        family="hq-momentum-hedged",
        version="v1.0",
    )
    engine = BacktestEngine(prices, BacktestConfig(leverage=1.0, cost=CostModel(), start="2010-01-01"))
    base = engine.run(signal)
    weights = signal._resolve_weights(prices).reindex(close.index).ffill().fillna(0.0)
    timing = apply_dual_valve_gating(
        baseline_returns=base.returns,
        volume=volume,
        weights=weights,
        trade_dates=close.index,
        style_window=40,
        panic_threshold=2.0,
        panic_leverage=0.2,
        smoothing_window=5,
    )
    return weights.mul(timing, axis=0), weights.mul(timing.shift(1).fillna(1.0), axis=0)


def build_reversal_composite_v10_weights(
    prices: PricePanel,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    amount: pd.DataFrame,
    total_mv: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    factor = compute_dsl_factor(close, volume, ast=AST_REVERSAL, cache_mode="disk")
    signal = Signal(
        factor=factor,
        top_n=25,
        direction=-1,
        rebalance_freq="20D",
        family="reversal-composite",
        version="v1.0",
    )
    engine = BacktestEngine(prices, BacktestConfig(leverage=1.0, cost=CostModel(), start="2010-01-01"))
    base = engine.run(signal)
    weights = signal._resolve_weights(prices).reindex(close.index).ffill().fillna(0.0)
    timing = apply_dual_valve_gating(
        baseline_returns=base.returns,
        volume=volume,
        weights=weights,
        trade_dates=close.index,
        style_window=40,
        panic_threshold=2.0,
        panic_leverage=0.2,
        smoothing_window=5,
    )
    return weights.mul(timing, axis=0), weights.mul(timing.shift(1).fillna(1.0), axis=0)


COMPOSITE_WEIGHT_RUNNERS: dict[tuple[str, str], CompositeWeightRunner] = {
    ("illiquidity", "v3.1"): build_illiquidity_v31_weights,
    ("hq-momentum-hedged", "v1.0"): build_hq_momentum_hedged_v10_weights,
    ("reversal-composite", "v1.0"): build_reversal_composite_v10_weights,
}
