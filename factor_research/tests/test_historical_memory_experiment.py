"""Historical cross-section memory experiment tests.

Run:
    cd factor_research && python3 -m pytest tests/test_historical_memory_experiment.py -q
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_toolkit import (  # noqa: E402
    build_historical_memory_factor,
    rank_ic_series,
    rolling_memory_rankic,
)


def _synthetic_panels():
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=80)
    codes = [f"S{i:02d}" for i in range(36)]

    pattern_a = pd.Series(np.linspace(-1.0, 1.0, len(codes)), index=codes)
    pattern_b = -pattern_a
    factor_rows = []
    label_rows = []
    for i, _ in enumerate(dates):
        pattern = pattern_a if (i // 5) % 2 == 0 else pattern_b
        noise = pd.Series(rng.normal(0, 0.75, len(codes)), index=codes)
        factor_rows.append(pattern + noise)
        label_rows.append(pattern * 0.02 + pd.Series(rng.normal(0, 0.0005, len(codes)), index=codes))

    factor = pd.DataFrame(factor_rows, index=dates)
    forward_ret = pd.DataFrame(label_rows, index=dates)
    return factor, forward_ret


def test_memory_factor_uses_shifted_features_and_only_matured_history():
    factor, forward_ret = _synthetic_panels()
    baseline = build_historical_memory_factor(
        factor,
        forward_ret,
        horizon=3,
        lookback=30,
        n_neighbors=4,
        min_history=4,
    )

    changed_today = factor.copy()
    changed_today.iloc[40] = changed_today.iloc[40] * -100.0
    same_signal = build_historical_memory_factor(
        changed_today,
        forward_ret,
        horizon=3,
        lookback=30,
        n_neighbors=4,
        min_history=4,
    )

    changed_immature_label = forward_ret.copy()
    changed_immature_label.iloc[39] = changed_immature_label.iloc[39] * -100.0
    same_without_immature_label = build_historical_memory_factor(
        factor,
        changed_immature_label,
        horizon=3,
        lookback=30,
        n_neighbors=4,
        min_history=4,
    )

    dt = factor.index[40]
    pd.testing.assert_series_equal(baseline.loc[dt], same_signal.loc[dt])
    pd.testing.assert_series_equal(baseline.loc[dt], same_without_immature_label.loc[dt])


def test_memory_factor_improves_rank_ic_on_repeating_cross_section_patterns():
    factor, forward_ret = _synthetic_panels()
    memory = build_historical_memory_factor(
        factor,
        forward_ret,
        horizon=1,
        lookback=40,
        n_neighbors=5,
        min_history=5,
    )

    base_ic = rank_ic_series(factor.shift(1), forward_ret).loc[memory.dropna(how="all").index].mean()
    memory_ic = rank_ic_series(memory, forward_ret).mean()

    assert memory_ic > base_ic + 0.05


def test_rolling_memory_rankic_reports_oos_windows_and_delta():
    factor, forward_ret = _synthetic_panels()
    result = rolling_memory_rankic(
        factor,
        forward_ret,
        horizon=1,
        lookback=30,
        n_neighbors=4,
        train_days=30,
        test_days=10,
        step_days=10,
        min_history=4,
    )

    assert len(result.windows) >= 3
    assert result.summary["rankic_delta"] > 0
    assert result.summary["windows"] == len(result.windows)
    assert result.summary["method"] == "historical_similar_cross_section_memory"
