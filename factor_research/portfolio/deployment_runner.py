"""Deployment-aware portfolio runners."""
from __future__ import annotations

import pandas as pd

from runtime.deployment import DeploymentNotReady, load_active_deployment, load_deployed_strategy_spec

from portfolio import research_catalog
from portfolio.research_catalog import _run_etf_trend


def run_active(start: str = "2018-01-01") -> dict[str, pd.Series]:
    """Run only legs from the validated DeploymentManifest, falling back to research ACTIVE legs."""
    try:
        deployment = load_active_deployment()
        out = {}
        for leg in deployment.legs:
            name = f"{leg.family}.{leg.version}"
            catalog = research_catalog.RESEARCH_STRATEGY_CATALOG.get(name)
            if catalog and catalog.get("fn"):
                out[name] = catalog["fn"](start)
                continue
            if leg.role == "equity_alpha":
                from core.engine import BacktestConfig, BacktestEngine, PricePanel
                from strategies.executable import build_executable_strategy
                from strategies.small_cap import load_price_panels

                strategy_spec = load_deployed_strategy_spec(leg)
                close, volume, amount = load_price_panels(start)
                prices = PricePanel(close=close, volume=volume, amount=amount)
                built = build_executable_strategy(strategy_spec, prices)
                out[name] = BacktestEngine(
                    prices,
                    BacktestConfig(start=start, leverage=1.0),
                ).run(built.signal).returns
                continue
            if leg.role == "defensive" and leg.family == "gov-bond-etf":
                out[name] = _run_etf_trend("511010", ma=60, start=start)
                continue
            raise RuntimeError(f"deployment leg has no canonical runner: {name}")
    except DeploymentNotReady:
        out = {}
        for name, spec in research_catalog.RESEARCH_STRATEGY_CATALOG.items():
            if spec.get("status") == "ACTIVE" and spec.get("fn"):
                out[name] = spec["fn"](start)
    return out


def active_strategies() -> list[str]:
    """Return deployed strategy names without running backtests."""
    try:
        dep = load_active_deployment()
        return [f"{leg.family}.{leg.version}" for leg in dep.legs]
    except DeploymentNotReady:
        return [
            n for n, s in research_catalog.RESEARCH_STRATEGY_CATALOG.items()
            if s.get("status") == "ACTIVE"
        ]


def defensive_strategies() -> set[str]:
    """Return ACTIVE defensive leg names for capped composition."""
    try:
        dep = load_active_deployment()
        return {
            f"{leg.family}.{leg.version}"
            for leg in dep.legs
            if leg.role == "defensive"
        }
    except DeploymentNotReady:
        return {
            n for n, s in research_catalog.RESEARCH_STRATEGY_CATALOG.items()
            if s.get("status") == "ACTIVE" and s.get("role") == "defensive"
        }
