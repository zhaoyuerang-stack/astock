"""Universe cost tiers + ADV impact research layer (ADR-033)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cost_impact import (
    adv_impact_for_aum,
    capacity_curve,
    multi_day_optimized_impact,
    square_root_slippage,
    summarize_capacity_limit,
)
from core.cost_tiers import (
    CostUniverse,
    formal_cost_for_universe,
    impact_assumption_bps,
    is_formal_universe,
    research_cost_for_universe,
)
from core.engine import CANONICAL_BUY_COST, CANONICAL_FINANCING_RATE, CANONICAL_SELL_COST, CostModel


def test_financing_rate_is_six_point_five_percent():
    assert CANONICAL_FINANCING_RATE == 0.065
    assert CostModel().financing_rate == 0.065
    assert formal_cost_for_universe("small_cap").financing_rate == 0.065


def test_formal_small_and_large_use_floors():
    small = formal_cost_for_universe("small_cap")
    large = formal_cost_for_universe("large_cap")
    assert small.buy_cost == CANONICAL_BUY_COST
    assert small.sell_cost == CANONICAL_SELL_COST
    assert large.buy_cost == CANONICAL_BUY_COST
    assert large.sell_cost == CANONICAL_SELL_COST


def test_formal_etf_rejected():
    with pytest.raises(ValueError, match="ETF"):
        formal_cost_for_universe("etf")


def test_research_profiles_etf_and_large_may_undercut_floor():
    etf = research_cost_for_universe("etf")
    assert etf.buy_cost == 0.0005
    assert etf.sell_cost == 0.0005
    large_r = research_cost_for_universe("large_cap")
    assert large_r.buy_cost < CANONICAL_BUY_COST
    assert large_r.sell_cost < CANONICAL_SELL_COST
    # research must not be confused with formal
    assert not is_formal_universe("etf")
    assert is_formal_universe("large_cap")


def test_impact_assumption_bps():
    assert impact_assumption_bps("small_cap") == pytest.approx(20.0)
    assert impact_assumption_bps("large_cap") == pytest.approx(10.0)
    assert impact_assumption_bps(CostUniverse.ETF) == pytest.approx(3.0)


def test_square_root_slippage_increases_with_participation():
    idx = pd.date_range("2020-01-01", periods=3, freq="B")
    cols = ["a"]
    part_lo = pd.DataFrame(0.01, index=idx, columns=cols)
    part_hi = pd.DataFrame(0.25, index=idx, columns=cols)
    vol = pd.DataFrame(0.02, index=idx, columns=cols)
    lo = square_root_slippage(part_lo, vol)
    hi = square_root_slippage(part_hi, vol)
    assert float(hi.iloc[-1, 0]) > float(lo.iloc[-1, 0])


def test_multi_day_split_not_worse_than_single_day():
    idx = pd.date_range("2020-01-01", periods=2, freq="B")
    single = pd.DataFrame(0.05, index=idx, columns=["a"])
    opt = multi_day_optimized_impact(single, max_days=5, alpha_decay=0.001)
    assert (opt <= single + 1e-12).all().all()


def test_adv_impact_and_capacity_curve_smoke():
    n, m = 40, 3
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    cols = [f"s{i}" for i in range(m)]
    rng = np.random.default_rng(0)
    close = pd.DataFrame(100 + rng.normal(0, 1, size=(n, m)).cumsum(axis=0), index=idx, columns=cols)
    amount = pd.DataFrame(1e8, index=idx, columns=cols)
    # rebalance every 5 days into equal weight
    weights = pd.DataFrame(0.0, index=idx, columns=cols)
    for i in range(0, n, 5):
        weights.iloc[i:] = 1.0 / m
    impact = adv_impact_for_aum(amount=amount, close=close, weights=weights, aum=50_000_000)
    assert len(impact) == n
    assert (impact >= 0).all()

    base = pd.Series(0.001, index=idx)
    curve = capacity_curve(
        base_returns=base,
        amount=amount,
        close=close,
        weights=weights,
        aum_scales=(5_000_000, 500_000_000),
    )
    assert "5000000" in curve and "500000000" in curve
    # higher AUM → more impact drag → lower net annual (weakly)
    assert curve["500000000"]["annual"] <= curve["5000000"]["annual"] + 1e-9

    limit, reasons = summarize_capacity_limit(
        {
            "5000000": {"aum": 5e6, "sharpe": 1.0, "annual": 0.2},
            "50000000": {"aum": 5e7, "sharpe": 0.2, "annual": 0.01},
        }
    )
    assert limit == 5e7
    assert reasons


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
