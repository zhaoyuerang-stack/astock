"""Compatibility layer — all implementations have moved to canonical modules.

.. deprecated::
    All functions in this module are re-exported from their canonical locations.
    New code should import directly from the modules listed below.

Canonical import paths
----------------------
- ``CostModel``              → ``core.engine.CostModel``
- ``StrategyConfig``         → ``strategies.small_cap.StrategyConfig``
- ``load_price_panels``      → ``strategies.small_cap.load_price_panels``
- ``small_cap_factor``       → ``factors.small_cap.small_cap_factor``
- ``small_cap_timing``       → ``factors.small_cap.small_cap_timing``
- ``build_rebalance_weights``→ ``strategies.small_cap.build_rebalance_weights``
- ``backtest_weights``       → ``strategies.small_cap.backtest_weights`` (deprecated proxy)
- ``run_small_cap_strategy`` → ``strategies.small_cap.run_small_cap_strategy``
- ``latest_signal``          → ``strategies.small_cap.latest_signal``
- ``metrics``                → ``engine.metrics.metrics``
- ``yearly_returns``         → ``engine.metrics.yearly_returns``
- ``safe_zscore``            → ``factors.utils.safe_zscore``
- ``mad_clip``               → ``factors.utils.mad_clip``

The unified backtest path is ``core.engine.BacktestEngine``.
"""

# ---------------------------------------------------------------------------
# Phase-2 canonical paths — new code should import from these directly
# ---------------------------------------------------------------------------
from core.engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    CostModel,
    PricePanel,
    Signal,
)
from engine.metrics import (
    metrics,
    yearly_returns,
    TARGET_ANNUAL,
    TARGET_MAXDD,
)
from factors.small_cap import (
    small_cap_factor,
    small_cap_timing,
)
from factors.utils import (
    mad_clip,
    safe_zscore,
)
from strategies.small_cap import (
    StrategyConfig,
    backtest_weights,
    build_rebalance_weights,
    latest_signal,
    load_price_panels,
    run_small_cap_strategy,
)
from strategies.size_earnings import (
    StrategyConfig as SizeEarningsConfig,
    build_factor,
    build_vol_target,
    run_strategy as run_size_earnings_strategy,
    latest_signal as size_earnings_latest_signal,
)

# Preserve the engine-based variant that test_engine.py imports
from strategies.small_cap import run_small_cap_strategy as run_small_cap_strategy_engine


__all__ = [
    "CostModel",
    "StrategyConfig",
    "load_price_panels",
    "small_cap_factor",
    "small_cap_timing",
    "build_rebalance_weights",
    "backtest_weights",
    "run_small_cap_strategy",
    "run_small_cap_strategy_engine",
    "latest_signal",
    "metrics",
    "yearly_returns",
    "safe_zscore",
    "mad_clip",
    "TARGET_ANNUAL",
    "TARGET_MAXDD",
    # Also re-export engine classes for convenience
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "PricePanel",
    "Signal",
]
