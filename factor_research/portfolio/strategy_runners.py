"""Backward-compatible exports for portfolio strategy runners.

New code should import from ``portfolio.research_catalog``,
``portfolio.deployment_runner``, or ``portfolio.runner_registry``.
"""
from __future__ import annotations

from portfolio.deployment_runner import active_strategies, defensive_strategies, run_active
from portfolio.research_catalog import (
    RESEARCH_STRATEGY_CATALOG,
    RESEARCH_STRATEGIES,
    _apply_registry_catalog_status,
    _f_illiquidity,
    _f_size_low_vol,
    _f_small_cap,
    _load_etf_close,
    _load_panels,
    _run_etf_trend,
    _run_with_factor,
    run_all_live,
    run_size_earnings,
    shadow_strategies,
)

__all__ = [
    "RESEARCH_STRATEGY_CATALOG",
    "RESEARCH_STRATEGIES",
    "_apply_registry_catalog_status",
    "_f_illiquidity",
    "_f_size_low_vol",
    "_f_small_cap",
    "_load_etf_close",
    "_load_panels",
    "_run_etf_trend",
    "_run_with_factor",
    "active_strategies",
    "defensive_strategies",
    "run_active",
    "run_all_live",
    "run_size_earnings",
    "shadow_strategies",
]
