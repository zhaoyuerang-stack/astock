"""Regression tests for benchmark-hedged Nine-Gate return semantics."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from core.analysis.nine_gates import GateReport, NineGatesEvaluator
from core.engine import PricePanel, Signal
from strategies import hq_momentum, large_cap


def _panels_and_factor() -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(20260710)
    dates = pd.bdate_range("2010-01-04", periods=560)
    codes = [f"{600000 + i:06d}" for i in range(8)]
    market = rng.normal(0.0002, 0.006, (len(dates), 1))
    alpha = np.linspace(0.0007, -0.0005, len(codes))[None, :]
    returns = market + alpha + rng.normal(0.0, 0.004, (len(dates), len(codes)))
    close = pd.DataFrame(
        10.0 * np.exp(np.cumsum(returns, axis=0)),
        index=dates,
        columns=codes,
    )
    amount = pd.DataFrame(
        rng.uniform(20_000_000, 80_000_000, close.shape),
        index=dates,
        columns=codes,
    )
    panels = {
        "close": close,
        "raw_close": close.copy(),
        "amount": amount,
    }
    universe = pd.DataFrame(False, index=dates, columns=codes)
    universe.loc[:, codes[:6]] = True
    scores = np.tile(np.linspace(2.0, -2.0, len(codes)), (len(dates), 1))
    factor = pd.DataFrame(scores, index=dates, columns=codes).where(universe)
    return panels, factor, universe


def _patch_strategy_inputs(monkeypatch):
    panels, factor, universe = _panels_and_factor()
    monkeypatch.setattr(large_cap, "load_clean_panels_with_growth", lambda: panels)
    monkeypatch.setattr(
        large_cap,
        "build_large_cap_premium_factor",
        lambda _panels, universe_size, w_cpv_max: (factor, universe),
    )

    # hq_momentum imports the loader inside the runner, so patch its source module.
    import factors.large_cap as large_cap_factors

    monkeypatch.setattr(large_cap_factors, "load_clean_panels_with_growth", lambda: panels)
    monkeypatch.setattr(
        hq_momentum,
        "build_hq_momentum_factor",
        lambda _panels, universe_size, lookback, q_filter_threshold: (factor, universe),
    )
    return panels, factor


def _evaluator(result: dict, factor: pd.DataFrame, leverage: float) -> tuple[NineGatesEvaluator, Signal]:
    close = result["close"]
    prices = PricePanel(
        close=close,
        volume=result["volume"],
        amount=result["amount"],
        raw_close=close,
    )
    evaluator = NineGatesEvaluator(
        prices=prices,
        factor_df=factor,
        thesis={"mechanism": "synthetic benchmark hedge", "citation": "test"},
        n_trials=3,
        portfolio_policy=result["portfolio_policy"],
        portfolio_leverage=leverage,
    )
    signal = Signal(
        weights=result["scheduled_weights"],
        timing=None,
        family="hedged-test",
        version="v1",
    )
    return evaluator, signal


def _manual_historical_formula(result: dict, factor: pd.DataFrame, config, *, timed: bool) -> pd.Series:
    """Independent replay of the pre-refactor strategy formula."""
    close = result["close"]
    universe = factor.notna()
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    benchmark = pd.Series(0.0, index=daily_ret.index)
    shifted = universe.shift(1)
    for date in daily_ret.index:
        active = shifted.loc[date].fillna(False).astype(bool)
        codes = active[active].index
        if len(codes):
            benchmark.loc[date] = daily_ret.loc[date, codes].mean()
    long_returns = result["engine_result"].returns
    common = long_returns.index.intersection(benchmark.index)
    neutral = long_returns.loc[common] - benchmark.loc[common] - config.hedge_cost_annual / 252.0
    if timed:
        nav = (1.0 + neutral).cumprod()
        timing = large_cap.large_cap_timing_hysteresis(
            nav,
            window=config.ma_window,
            buffer=config.buffer_size,
        )
        transitions = timing.diff().fillna(0.0).ne(0.0)
        final = neutral * timing - config.switch_friction * transitions
    else:
        final = neutral
    return final.loc[pd.Timestamp(config.start):]


@pytest.mark.parametrize("strategy_name", ["large_cap", "hq_momentum"])
def test_gate5_and_gate6_replay_exact_strategy_runner_returns(monkeypatch, strategy_name):
    panels, factor = _patch_strategy_inputs(monkeypatch)
    start = str(panels["close"].index[170].date())
    if strategy_name == "large_cap":
        config = large_cap.StrategyConfig(
            start=start,
            top_n=2,
            rebalance_days=10,
            ma_window=20,
            buffer_size=0.0,
        )
        result = large_cap.run_large_cap_strategy(config)
    else:
        config = hq_momentum.StrategyConfig(
            start=start,
            top_n=2,
            rebalance_days=10,
        )
        result = hq_momentum.run_hq_momentum_strategy(config)

    manual = _manual_historical_formula(
        result,
        factor,
        config,
        timed=strategy_name == "large_cap",
    )
    pd.testing.assert_series_equal(result["returns"], manual, check_names=False)

    evaluator, signal = _evaluator(result, factor, config.leverage)
    _, gate5_result = evaluator.run_gate5_backtest(signal, start=config.start)

    pd.testing.assert_series_equal(
        gate5_result.returns,
        result["returns"],
        check_names=False,
        atol=1e-14,
        rtol=0.0,
    )
    assert not gate5_result.returns.equals(result["long_returns"])

    gate6 = evaluator.run_gate6_cost_capacity(signal, start=config.start)
    assert gate6.metrics["annual_1x"] == pytest.approx(
        result["returns"].mean() * 252,
        abs=1e-14,
    )


def test_gate4_and_persisted_gate5_series_use_hedged_runner_returns(monkeypatch):
    panels, factor = _patch_strategy_inputs(monkeypatch)
    config = hq_momentum.StrategyConfig(
        start=str(panels["close"].index[170].date()),
        top_n=2,
        rebalance_days=10,
    )
    result = hq_momentum.run_hq_momentum_strategy(config)
    evaluator, signal = _evaluator(result, factor, config.leverage)
    captured: dict[str, pd.Series] = {}

    def report(gate_id, metrics=None):
        return GateReport(gate_id, "stub", True, "PASS", metrics or {}, "stub", [])

    evaluator.run_gate0_data_audit = lambda: report(0)
    evaluator.run_gate1_hypothesis = lambda: report(1)
    evaluator.run_gate2_single_factor = lambda: report(2, {"ic_mean": 0.01})
    evaluator.run_gate3_neutralization = lambda: report(3)

    def capture_gate4(_observed_sr, returns):
        captured["returns"] = returns.copy()
        return report(4)

    evaluator.run_gate4_multiple_testing = capture_gate4
    evaluator.run_gate6_cost_capacity = lambda _signal, _start: report(6)
    evaluator.run_gate7_stress_testing = lambda _signal, _start: report(7)
    evaluator.run_gate7a_purged_embargoed_cv = lambda _signal, _start: report("7A")
    evaluator.run_gate8_live_monitoring = lambda _summary: report(8)

    evaluator.evaluate_all(signal, start=config.start)
    pd.testing.assert_series_equal(captured["returns"], result["returns"], check_names=False)
    pd.testing.assert_series_equal(evaluator.gate5_returns, result["returns"], check_names=False)


def test_gate7_regime_metrics_are_computed_from_hedged_not_long_returns(monkeypatch):
    panels, factor = _patch_strategy_inputs(monkeypatch)
    config = large_cap.StrategyConfig(
        start=str(panels["close"].index[170].date()),
        top_n=2,
        rebalance_days=10,
        ma_window=20,
        buffer_size=0.0,
    )
    result = large_cap.run_large_cap_strategy(config)
    evaluator, signal = _evaluator(result, factor, config.leverage)
    test_start = panels["close"].index[250]
    test_end = panels["close"].index[420]
    import core.analysis.nine_gates as nine_gates_module

    monkeypatch.setattr(
        nine_gates_module,
        "walk_forward_windows",
        lambda *_args, **_kwargs: [{
            "train_start": panels["close"].index[0],
            "train_end": panels["close"].index[220],
            "test_start": test_start,
            "test_end": test_end,
        }],
    )
    gate7 = evaluator.run_gate7_stress_testing(signal, start=config.start)

    expected_oos = result["returns"].loc[test_start:test_end]
    assert gate7.metrics["wf_annual"] == pytest.approx(expected_oos.mean() * 252, abs=1e-14)

    mkt_ret = evaluator.daily_returns.mean(axis=1)
    mkt_idx = (1.0 + mkt_ret).cumprod()
    bull = mkt_idx > mkt_idx.rolling(16).mean()
    common = result["returns"].index.intersection(bull.index)
    bull_rets = result["returns"].loc[common][bull.loc[common]]
    bear_rets = result["returns"].loc[common][~bull.loc[common]]
    assert gate7.metrics["bull_annual"] == pytest.approx(bull_rets.mean() * 252, abs=1e-14)
    assert gate7.metrics["bear_annual"] == pytest.approx(bear_rets.mean() * 252, abs=1e-14)


def test_hedged_evaluator_rejects_double_timing(monkeypatch):
    panels, factor = _patch_strategy_inputs(monkeypatch)
    config = large_cap.StrategyConfig(
        start=str(panels["close"].index[170].date()),
        top_n=2,
        rebalance_days=10,
        ma_window=20,
    )
    result = large_cap.run_large_cap_strategy(config)
    evaluator, signal = _evaluator(result, factor, config.leverage)
    signal.timing = result["timing"]

    with pytest.raises(ValueError, match="untimed long-leg Signal"):
        evaluator.run_gate5_backtest(signal, start=config.start)


def test_hedged_policy_rejects_incomplete_benchmark(monkeypatch):
    panels, factor = _patch_strategy_inputs(monkeypatch)
    config = hq_momentum.StrategyConfig(
        start=str(panels["close"].index[170].date()),
        top_n=2,
        rebalance_days=10,
    )
    result = hq_momentum.run_hq_momentum_strategy(config)
    broken = replace(
        result["portfolio_policy"],
        benchmark_returns=result["portfolio_policy"].benchmark_returns.drop(
            result["engine_result"].returns.index[10]
        ),
    )

    with pytest.raises(ValueError, match="benchmark is missing"):
        broken.apply(result["engine_result"], statistics_start=config.start)
