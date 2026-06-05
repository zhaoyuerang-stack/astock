"""Smoke tests for the unified ``core.engine.BacktestEngine``.

Run::

    cd /Users/kiki/astcok/factor_research && /usr/bin/python3 test_engine.py

All tests must pass before the Phase-2 migration is considered complete.
"""
import os
import sys
from pathlib import Path

os.chdir(Path(__file__).parent)

import numpy as np
import pandas as pd

from core.backtest import (
    StrategyConfig,
    backtest_weights,
    build_rebalance_weights,
    load_price_panels,
    metrics,
    run_small_cap_strategy,
    small_cap_factor,
    small_cap_timing,
)
from core.engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    PricePanel,
    Signal,
)


def _make_test_signal_weights():
    """Minimal fixture: load real data, build small-cap weights."""
    close, volume, amount = load_price_panels("2018-01-01")
    factor = small_cap_factor(amount, 60)
    timing, _, _ = small_cap_timing(close, amount, 16)
    weights = build_rebalance_weights(factor, close, 25, 20)
    return close, weights, timing


# ---------------------------------------------------------------------------
# Test 1: BacktestResult.metrics matches core.backtest.metrics()
# ---------------------------------------------------------------------------

def test_backtest_result_metrics():
    """Engine result.metrics must equal legacy metrics() function."""
    result = run_small_cap_strategy()
    ret = result["returns"]

    legacy = metrics(ret)
    engine_result = BacktestResult(returns=ret, turnover=result["detail"]["turnover"],
                                    cost=result["detail"]["cost"])
    modern = engine_result.metrics

    assert np.isclose(modern["annual"], legacy["annual"], atol=1e-10)
    assert np.isclose(modern["sharpe"], legacy["sharpe"], atol=1e-10)
    assert np.isclose(modern["maxdd"], legacy["maxdd"], atol=1e-10)
    assert np.isclose(modern["calmar"], legacy["calmar"], atol=1e-10)
    assert modern["hit"] == legacy["hit"]
    print("✅ test_backtest_result_metrics passed")


# ---------------------------------------------------------------------------
# Test 2: Engine.run(weights) == legacy backtest_weights()
# ---------------------------------------------------------------------------

def test_engine_run_weights():
    """BacktestEngine.run with pre-computed weights must match legacy backtest_weights."""
    close, weights_dict, timing = _make_test_signal_weights()
    prices = PricePanel(close=close, volume=pd.DataFrame(), amount=pd.DataFrame())
    config = BacktestConfig(start="2018-01-01")
    engine = BacktestEngine(prices=prices, config=config)

    # Legacy path
    ret_legacy, detail_legacy = backtest_weights(close, weights_dict, timing)

    # Engine path
    signal = Signal(weights=weights_dict, timing=timing)
    result = engine._run_weight_backtest(weights_dict, timing, signal)

    pd.testing.assert_series_equal(result.returns, ret_legacy, check_names=False)
    pd.testing.assert_frame_equal(result.detail, detail_legacy, check_names=False)
    print("✅ test_engine_run_weights passed")


# ---------------------------------------------------------------------------
# Test 3: Engine.run(factor) == weights path
# ---------------------------------------------------------------------------

def test_engine_run_factor():
    """Signal(factor=...) via engine must match Signal(weights=...) via engine."""
    close, volume, amount = load_price_panels("2018-01-01")
    factor = small_cap_factor(amount, 60)
    timing, _, _ = small_cap_timing(close, amount, 16)
    weights_dict = build_rebalance_weights(factor, close, 25, 20)

    prices = PricePanel(close=close, volume=volume, amount=amount)
    config = BacktestConfig(start="2018-01-01")
    engine = BacktestEngine(prices=prices, config=config)

    result_weights = engine.run(Signal(weights=weights_dict, timing=timing))
    result_factor = engine.run(Signal(factor=factor, top_n=25, rebalance_freq="20D", timing=timing))

    # Factor path may have slight date-alignment differences at boundaries;
    # compare on common dates only.
    common = result_weights.returns.index.intersection(result_factor.returns.index)
    assert len(common) > 1000, f"Only {len(common)} common dates"
    np.testing.assert_allclose(
        result_weights.returns.loc[common].values,
        result_factor.returns.loc[common].values,
        atol=1e-10,
    )
    print("✅ test_engine_run_factor passed")


# ---------------------------------------------------------------------------
# Test 4: BacktestResult properties are consistent
# ---------------------------------------------------------------------------

def test_backtest_result_properties():
    """Derived properties must be internally consistent."""
    result = run_small_cap_strategy()
    ret = result["returns"]
    engine_result = BacktestResult(returns=ret, turnover=result["detail"]["turnover"],
                                    cost=result["detail"]["cost"])

    assert engine_result.n == len(ret)
    assert engine_result.sharpe == engine_result.annual / engine_result.vol if engine_result.vol > 0 else True
    assert engine_result.calmar == engine_result.annual / abs(engine_result.maxdd) if engine_result.maxdd < 0 else True
    print("✅ test_backtest_result_properties passed")


# ---------------------------------------------------------------------------
# Test 5: run_small_cap_strategy_engine() matches run_small_cap_strategy()
# ---------------------------------------------------------------------------

def test_small_cap_strategy_engine():
    """The engine-based small-cap wrapper must match the legacy implementation."""
    from core.backtest import run_small_cap_strategy_engine

    legacy = run_small_cap_strategy()
    modern = run_small_cap_strategy_engine()

    pd.testing.assert_series_equal(legacy["returns"], modern["returns"], check_names=False)
    pd.testing.assert_frame_equal(legacy["detail"], modern["detail"], check_names=False)
    print("✅ test_small_cap_strategy_engine passed")


# ---------------------------------------------------------------------------
# Test 6: Compatibility layer — engine/backtest.py still importable
# ---------------------------------------------------------------------------

def test_engine_backtest_compat():
    """``engine.factor_analysis`` is the canonical path for factor diagnostics."""
    from engine.factor_analysis import calc_ic, ic_summary, stratify_return
    assert callable(calc_ic)
    assert callable(ic_summary)
    assert callable(stratify_return)
    print("✅ test_engine_backtest_compat passed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running core.engine smoke tests...\n")
    test_backtest_result_metrics()
    test_engine_run_weights()
    test_engine_run_factor()
    test_backtest_result_properties()
    test_small_cap_strategy_engine()
    test_engine_backtest_compat()
    print("\n🎉 All tests passed!")
