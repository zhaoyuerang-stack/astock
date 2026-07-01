"""Composite promotion leg specification tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow.composite_spec import CompositeLegSpec, parse_composite_allocation


def test_parse_family_version_allocation():
    legs = parse_composite_allocation(
        "illiquidity/v3.1:0.40,hq-momentum-hedged/v1.0:0.40,small-cap-size/v2.0:0.20"
    )

    assert legs == [
        CompositeLegSpec("illiquidity", "v3.1", 0.40, "equity_alpha"),
        CompositeLegSpec("hq-momentum-hedged", "v1.0", 0.40, "equity_alpha"),
        CompositeLegSpec("small-cap-size", "v2.0", 0.20, "equity_alpha"),
    ]


def test_parse_legacy_aliases_as_explicit_mapping():
    legs = parse_composite_allocation("illiq_sc:0.40,lc_mom:0.40,reversal:0.20")

    assert [(x.family, x.version, x.weight, x.alias) for x in legs] == [
        ("illiquidity", "v3.1", 0.40, "illiq_sc"),
        ("hq-momentum-hedged", "v1.0", 0.40, "lc_mom"),
        ("reversal-composite", "v1.0", 0.20, "reversal"),
    ]


def test_rejects_weights_that_do_not_sum_to_one():
    with pytest.raises(ValueError, match="sum"):
        parse_composite_allocation("illiquidity/v3.1:0.70,small-cap-size/v2.0:0.20")


def test_rejects_unknown_alias_or_malformed_leg():
    with pytest.raises(ValueError, match="unknown"):
        parse_composite_allocation("ghost:1.0")
    with pytest.raises(ValueError, match="family/version"):
        parse_composite_allocation("illiquidity:1.0")


def test_promote_composite_accepts_family_version_allocation():
    from workflow.promote_composite import parse_allocation

    assert parse_allocation("illiquidity/v3.1:0.40,hq-momentum-hedged/v1.0:0.40,reversal-composite/v1.0:0.20") == {
        "illiquidity/v3.1": 0.40,
        "hq-momentum-hedged/v1.0": 0.40,
        "reversal-composite/v1.0": 0.20,
    }


def test_runner_registry_resolves_composite_weight_runners():
    from portfolio.runner_registry import get_composite_weight_runner

    assert get_composite_weight_runner(CompositeLegSpec("illiquidity", "v3.1", 0.40)) is not None
    assert get_composite_weight_runner(CompositeLegSpec("hq-momentum-hedged", "v1.0", 0.40)) is not None
    assert get_composite_weight_runner(CompositeLegSpec("reversal-composite", "v1.0", 0.20)) is not None
    assert get_composite_weight_runner(CompositeLegSpec("missing", "v1.0", 1.0)) is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
