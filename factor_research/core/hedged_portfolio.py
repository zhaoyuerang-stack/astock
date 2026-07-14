"""Canonical post-processing for benchmark-hedged strategy returns.

The stock book is always simulated by :class:`core.engine.BacktestEngine`.
This module then applies the same benchmark short, hedge carry, and optional
NAV-timing overlay to both production strategy runners and Nine-Gate replays.
Keeping that return transform in one place prevents an audit from silently
grading the long leg while production reports a hedged portfolio.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

import numpy as np
import pandas as pd

from core.engine import BacktestResult


TimingBuilder = Callable[[pd.Series], pd.Series]


def equal_weight_universe_returns(
    close: pd.DataFrame,
    universe: pd.DataFrame,
) -> pd.Series:
    """Return the lagged-membership equal-weight benchmark used by hedged books.

    Membership is shifted one trading row before it is applied.  Missing stock
    returns are treated exactly as the strategy runners historically treated
    them: the close-to-close panel is sanitized first, then active names are
    averaged.  Days with no active names have zero benchmark return.
    """
    daily_ret = (
        close.pct_change(fill_method=None)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    membership = (
        universe.reindex(index=daily_ret.index, columns=daily_ret.columns)
        .shift(1)
        .fillna(False)
        .astype(bool)
    )
    benchmark = daily_ret.where(membership).mean(axis=1).fillna(0.0)
    benchmark.name = "benchmark_return"
    return benchmark


@dataclass(frozen=True)
class HedgedPortfolioResult:
    """Final portfolio result plus its mechanically reconciled return legs."""

    result: BacktestResult
    long_returns: pd.Series
    benchmark_returns: pd.Series
    neutral_returns: pd.Series
    timing: pd.Series


@dataclass(frozen=True)
class HedgedReturnPolicy:
    """Post-process a canonical long-book result into a benchmark hedge.

    ``warmup_start`` is the simulation/statistics start needed before applying
    a path-dependent timing rule.  Nine-Gate temporarily runs the long book
    from this date and slices only after this policy has built neutral NAV.
    """

    benchmark_returns: pd.Series
    hedge_cost_annual: float
    timing_builder: TimingBuilder | None = None
    switch_friction: float = 0.0
    warmup_start: str = "2010-01-01"

    def __post_init__(self) -> None:
        for label, value in (
            ("hedge_cost_annual", self.hedge_cost_annual),
            ("switch_friction", self.switch_friction),
        ):
            if not np.isfinite(value) or float(value) < 0.0:
                raise ValueError(f"{label} must be a finite non-negative cost")
        if not isinstance(self.benchmark_returns.index, pd.DatetimeIndex):
            raise TypeError("hedged benchmark must use a DatetimeIndex")
        if not self.benchmark_returns.index.is_monotonic_increasing:
            raise ValueError("hedged benchmark index must be monotonic increasing")
        if self.benchmark_returns.index.has_duplicates:
            raise ValueError("hedged benchmark index must be unique")

    def apply(
        self,
        long_result: BacktestResult,
        *,
        statistics_start: str | pd.Timestamp | None = None,
    ) -> HedgedPortfolioResult:
        """Apply hedge semantics and return a new canonical ``BacktestResult``."""
        missing_dates = long_result.returns.index.difference(self.benchmark_returns.index)
        if len(missing_dates):
            raise ValueError(
                f"hedged benchmark is missing {len(missing_dates)} long-book dates"
            )
        common = long_result.returns.index
        if common.empty:
            raise ValueError("cannot apply hedged return policy to an empty long-book result")

        long_returns = long_result.returns.loc[common].astype(float)
        benchmark = self.benchmark_returns.reindex(common)
        invalid_benchmark = ~np.isfinite(benchmark.to_numpy(dtype=float))
        if invalid_benchmark.any():
            missing = int(invalid_benchmark.sum())
            raise ValueError(f"hedged benchmark has {missing} missing/non-finite observations")

        daily_hedge_cost = float(self.hedge_cost_annual) / 252.0
        neutral = long_returns - benchmark - daily_hedge_cost

        if self.timing_builder is None:
            timing = pd.Series(1.0, index=common, name="hedged_timing")
        else:
            neutral_nav = (1.0 + neutral).cumprod()
            timing = self.timing_builder(neutral_nav).reindex(common)
            timing = timing.astype(float)
            invalid_timing = ~np.isfinite(timing.to_numpy(dtype=float))
            if invalid_timing.any() or ((timing < 0.0) | (timing > 1.0)).any():
                raise ValueError("hedged timing builder returned missing or out-of-range exposure")
            timing.name = "hedged_timing"

        transitions = timing.diff().fillna(0.0).ne(0.0)
        final_returns = neutral * timing - float(self.switch_friction) * transitions.astype(float)

        long_cost = long_result.cost.reindex(common).fillna(0.0)
        effective_cost = (
            (long_cost + daily_hedge_cost) * timing
            + float(self.switch_friction) * transitions.astype(float)
        )
        turnover = long_result.turnover.reindex(common).fillna(0.0)

        if statistics_start is not None:
            start = pd.Timestamp(statistics_start)
            keep = common >= start
            long_returns = long_returns.loc[keep]
            benchmark = benchmark.loc[keep]
            neutral = neutral.loc[keep]
            timing = timing.loc[keep]
            final_returns = final_returns.loc[keep]
            effective_cost = effective_cost.loc[keep]
            turnover = turnover.loc[keep]

        config = long_result.config
        if config is not None and statistics_start is not None:
            config = replace(config, start=str(pd.Timestamp(statistics_start).date()))
        result = BacktestResult(
            returns=final_returns,
            turnover=turnover,
            cost=effective_cost,
            weights_history=long_result.weights_history,
            family=long_result.family,
            version=long_result.version,
            config=config,
        )
        return HedgedPortfolioResult(
            result=result,
            long_returns=long_returns,
            benchmark_returns=benchmark,
            neutral_returns=neutral,
            timing=timing,
        )
