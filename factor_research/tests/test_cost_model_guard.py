"""Regression tests for the formal-path cost floor (R-COST-001 / audit #8)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.engine import (
    CANONICAL_BUY_COST,
    CANONICAL_SELL_COST,
    CostModel,
    formal_cost_model,
)
from scripts.ci.check_cost_model_usage import scan_source


def test_rejects_free_long_leg():
    src = "cost = CostModel(buy_cost=0.0, sell_cost=0.0, financing_rate=0.0)"
    violations = scan_source(src, rel="strategies/example.py")
    assert len(violations) == 1
    assert "buy_cost=0.0" in violations[0]
    assert "sell_cost=0.0" in violations[0]


def test_rejects_optimistic_etf_five_bp():
    """Audit #8: low-positive etf 5bp must not pass the formal-path guard."""
    src = "cost = CostModel(buy_cost=0.0005, sell_cost=0.0005, financing_rate=0.0)"
    violations = scan_source(src, rel="strategies/industry_rotation.py")
    assert len(violations) == 1
    assert "0.0005" in violations[0]


def test_rejects_free_long_leg_hidden_behind_constant_alias():
    src = "FREE = 0.0\ncost = CostModel(buy_cost=FREE, sell_cost=FREE)"
    violations = scan_source(src, rel="strategies/example.py")
    assert len(violations) == 1


def test_rejects_half_canonical_literal():
    src = "cost = CostModel(buy_cost=0.001125, sell_cost=0.001375)"
    violations = scan_source(src, rel="workflow/phase2_backtest.py")
    assert len(violations) == 1


def test_allows_canonical_default():
    assert scan_source("cost = CostModel()", rel="strategies/example.py") == []


def test_allows_explicit_canonical_costs():
    src = (
        f"cost = CostModel(buy_cost={CANONICAL_BUY_COST}, "
        f"sell_cost={CANONICAL_SELL_COST}, financing_rate=0.0)"
    )
    assert scan_source(src, rel="strategies/example.py") == []


def test_allows_stress_above_floor():
    src = "cost = CostModel(buy_cost=0.0045, sell_cost=0.0055, financing_rate=0.065)"
    assert scan_source(src, rel="core/analysis/nine_gates.py") == []


def test_formal_cost_model_defaults_and_stress():
    base = formal_cost_model()
    assert base.buy_cost == CANONICAL_BUY_COST
    assert base.sell_cost == CANONICAL_SELL_COST

    stressed = formal_cost_model(buy_cost=0.0045, sell_cost=0.0055)
    assert stressed.buy_cost == 0.0045
    assert stressed.sell_cost == 0.0055


def test_formal_cost_model_rejects_undercut():
    with pytest.raises(ValueError, match="R-COST-001"):
        formal_cost_model(buy_cost=0.0005, sell_cost=0.0005)
    with pytest.raises(ValueError, match="R-COST-001"):
        formal_cost_model(buy_cost=0.00225, sell_cost=0.001)  # sell under floor
    # config injection shape used by pre-fix phase2
    with pytest.raises(ValueError, match="R-COST-001"):
        formal_cost_model(buy_cost=0.0001, sell_cost=0.00275)


def test_formal_cost_model_accepts_explicit_none_keys():
    """phase2/3 pass config.get which may be missing → None → floors."""
    c = formal_cost_model(buy_cost=None, sell_cost=None, financing_rate=None)
    assert c == CostModel()


def test_phase2_runner_rejects_undercut_config():
    from workflow.phase2_backtest import Phase2Runner

    def _fb(*_a, **_k):
        raise AssertionError("should not run")

    def _tb(*_a, **_k):
        raise AssertionError("should not run")

    with pytest.raises(ValueError, match="R-COST-001"):
        Phase2Runner(
            factor_builder=_fb,
            timing_builder=_tb,
            family="unit",
            config={"buy_cost": 0.0005, "sell_cost": 0.0005},
        )


if __name__ == "__main__":
    import pytest as _pytest
    sys.exit(_pytest.main([__file__, "-q"]))
