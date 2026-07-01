"""Registry facade for research and deployment portfolio runners."""
from __future__ import annotations

from portfolio import research_catalog
from portfolio.composite_weight_runners import COMPOSITE_WEIGHT_RUNNERS, CompositeWeightRunner
from portfolio.runner_protocol import RunnerFn


def get_research_runner(name: str) -> RunnerFn | None:
    spec = research_catalog.RESEARCH_STRATEGY_CATALOG.get(name)
    if not spec:
        return None
    return spec.get("fn")


def research_runner_names() -> list[str]:
    return list(research_catalog.RESEARCH_STRATEGY_CATALOG.keys())


def get_composite_weight_runner(leg) -> CompositeWeightRunner | None:
    return COMPOSITE_WEIGHT_RUNNERS.get((leg.family, leg.version))
