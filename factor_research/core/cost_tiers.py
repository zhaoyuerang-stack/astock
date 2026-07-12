"""Universe-stratified trading-cost profiles (R-COST-001).

Three layers, different evidence rights:

1. **small_cap formal** — default admission floor (canonical CostModel).
2. **large_cap formal** — same floor for register/promote (cannot undercut);
   research may use a milder *impact decomposition* for comparison only.
3. **etf research** — lower explicit fees for sensitivity / live-ETF studies;
   **never** formal admission evidence.

Formal evidence always goes through :func:`formal_cost_for_universe` which
delegates to :func:`core.engine.formal_cost_model` and refuses ETF.
"""
from __future__ import annotations

from enum import Enum
from typing import Mapping

from core.engine import (
    CANONICAL_BUY_COST,
    CANONICAL_FINANCING_RATE,
    CANONICAL_SELL_COST,
    CostModel,
    formal_cost_model,
)


class CostUniverse(str, Enum):
    """Strategy universe for cost profile selection."""

    SMALL_CAP = "small_cap"
    LARGE_CAP = "large_cap"
    ETF = "etf"


# Fixed A-share components (approx, for documentation / research decomposition).
# Commission ~0.65bp, transfer ~0.1bp; stamp 5bp sell-only.
FIXED_BUY = 0.000075   # commission + transfer
FIXED_SELL = 0.000575  # commission + transfer + stamp 5bp

# Constant impact assumptions embedded in the one-sided formal rates.
IMPACT_SMALL_CAP = 0.0020   # 20bp — small/micro prudent
IMPACT_LARGE_CAP = 0.0010   # 10bp — liquid large-cap research
IMPACT_ETF = 0.0003         # 3bp — ETF research only

# Research (non-formal) one-sided rates = fixed + impact.
# Large-cap / ETF research may sit *below* formal floors; must not register.
_RESEARCH_PROFILES: Mapping[CostUniverse, CostModel] = {
    CostUniverse.SMALL_CAP: CostModel(
        buy_cost=CANONICAL_BUY_COST,
        sell_cost=CANONICAL_SELL_COST,
        financing_rate=CANONICAL_FINANCING_RATE,
    ),
    CostUniverse.LARGE_CAP: CostModel(
        buy_cost=round(FIXED_BUY + IMPACT_LARGE_CAP, 6),   # ~0.001075
        sell_cost=round(FIXED_SELL + IMPACT_LARGE_CAP, 6),  # ~0.001575
        financing_rate=CANONICAL_FINANCING_RATE,
    ),
    CostUniverse.ETF: CostModel(
        buy_cost=0.0005,
        sell_cost=0.0005,
        financing_rate=0.0,
    ),
}


def parse_cost_universe(value: str | CostUniverse | None) -> CostUniverse:
    if value is None or value == "":
        return CostUniverse.SMALL_CAP
    if isinstance(value, CostUniverse):
        return value
    key = str(value).strip().lower().replace("-", "_")
    aliases = {
        "small": CostUniverse.SMALL_CAP,
        "small_cap": CostUniverse.SMALL_CAP,
        "micro": CostUniverse.SMALL_CAP,
        "large": CostUniverse.LARGE_CAP,
        "large_cap": CostUniverse.LARGE_CAP,
        "mega": CostUniverse.LARGE_CAP,
        "etf": CostUniverse.ETF,
        "fund": CostUniverse.ETF,
    }
    if key not in aliases:
        raise ValueError(
            f"unknown cost universe {value!r}; "
            f"expected one of {sorted(set(aliases))}"
        )
    return aliases[key]


def formal_cost_for_universe(
    universe: str | CostUniverse | None = CostUniverse.SMALL_CAP,
    *,
    buy_cost: float | None = None,
    sell_cost: float | None = None,
    financing_rate: float | None = None,
) -> CostModel:
    """CostModel allowed on formal / promote / phase2-3 / registry evidence.

    - ``small_cap`` and ``large_cap``: canonical floors (or higher stress via kwargs).
    - ``etf``: always rejected — ETF fees are research-sensitivity only.
    """
    u = parse_cost_universe(universe)
    if u is CostUniverse.ETF:
        raise ValueError(
            "R-COST-001: ETF cost profile is research-sensitivity only; "
            "formal admission must use small_cap/large_cap floors via "
            "formal_cost_model / formal_cost_for_universe"
        )
    # Large-cap formal still cannot undercut the small-cap floor (anti-self-deception).
    return formal_cost_model(
        buy_cost=buy_cost,
        sell_cost=sell_cost,
        financing_rate=financing_rate,
    )


def research_cost_for_universe(
    universe: str | CostUniverse | None = CostUniverse.SMALL_CAP,
) -> CostModel:
    """Named research profiles (may sit below formal floors for large_cap/ETF).

    Output must **not** be used as standalone/register evidence. Prefer
    :func:`formal_cost_for_universe` on any promote/phase path.
    """
    u = parse_cost_universe(universe)
    return _RESEARCH_PROFILES[u]


def impact_assumption_bps(universe: str | CostUniverse | None) -> float:
    """Documented constant impact (bps, one side) for the universe tier."""
    u = parse_cost_universe(universe)
    return {
        CostUniverse.SMALL_CAP: IMPACT_SMALL_CAP * 1e4,
        CostUniverse.LARGE_CAP: IMPACT_LARGE_CAP * 1e4,
        CostUniverse.ETF: IMPACT_ETF * 1e4,
    }[u]


def is_formal_universe(universe: str | CostUniverse | None) -> bool:
    u = parse_cost_universe(universe)
    return u in {CostUniverse.SMALL_CAP, CostUniverse.LARGE_CAP}
