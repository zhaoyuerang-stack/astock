"""Candidate strategy definitions and grid generation for the stage-1 factory."""
from dataclasses import dataclass, asdict
from typing import Sequence

import numpy as np

from core.backtest import mad_clip, safe_zscore, small_cap_factor


@dataclass(frozen=True)
class Candidate:
    family: str
    version: str
    desc: str
    factors: Sequence[str]
    weights: Sequence[float]
    top_n: int = 25
    rebalance_days: int = 20
    leverage: float = 1.0
    timing: str = "small_cap_ma16"

    def to_dict(self):
        return asdict(self)


def factor_library(close, volume, amount):
    ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    return {
        "size20": small_cap_factor(amount, 20),
        "size40": small_cap_factor(amount, 40),
        "size60": small_cap_factor(amount, 60),
        "low_vol10": safe_zscore(mad_clip(-ret.rolling(10).std())),
        "low_vol20": safe_zscore(mad_clip(-ret.rolling(20).std())),
        "low_vol40": safe_zscore(mad_clip(-ret.rolling(40).std())),
        "reversal10": safe_zscore(mad_clip(-(close / close.shift(10) - 1))),
        "reversal20": safe_zscore(mad_clip(-(close / close.shift(20) - 1))),
        "reversal5": safe_zscore(mad_clip(-(close / close.shift(5) - 1))),
        "momentum_quality10": safe_zscore(mad_clip((ret > 0).rolling(10).mean())),
        "momentum_quality20": safe_zscore(mad_clip((ret > 0).rolling(20).mean())),
        "momentum_quality40": safe_zscore(mad_clip((ret > 0).rolling(40).mean())),
        "low_turnover5": safe_zscore(
            mad_clip(-(amount / (amount.rolling(60).mean() + 1e-6)).rolling(5).mean())
        ),
        "low_turnover10": safe_zscore(
            mad_clip(-(amount / (amount.rolling(60).mean() + 1e-6)).rolling(10).mean())
        ),
        "low_turnover20": safe_zscore(
            mad_clip(-(amount / (amount.rolling(60).mean() + 1e-6)).rolling(20).mean())
        ),
        "price_below_ma20": safe_zscore(mad_clip(-(close / close.rolling(20).mean() - 1))),
        "price_below_ma60": safe_zscore(mad_clip(-(close / close.rolling(60).mean() - 1))),
    }


def build_factor(candidate, library):
    total = sum(abs(w) for w in candidate.weights) or 1.0
    comp = 0
    for name, weight in zip(candidate.factors, candidate.weights):
        comp = comp + library[name] * (weight / total)
    return safe_zscore(comp)


def default_candidates():
    """Small first batch: enough to validate the factory, not a search yet."""
    return [
        Candidate("small-cap-size", "factory-baseline", "小盘60基线", ["size60"], [1.0], leverage=1.25),
        Candidate("low-vol", "v0.1", "低波20", ["low_vol20"], [1.0]),
        Candidate("reversal", "v0.1", "20日反转", ["reversal20"], [1.0]),
        Candidate("reversal", "v0.2", "5日反转", ["reversal5"], [1.0]),
        Candidate("momentum-quality", "v0.1", "上涨天数质量", ["momentum_quality20"], [1.0]),
        Candidate("liquidity-flow", "v0.1", "低换手/低关注", ["low_turnover10"], [1.0]),
        Candidate("mean-reversion-quality", "v0.1", "小盘+低波+反转", ["size60", "low_vol20", "reversal20"], [0.4, 0.3, 0.3]),
        Candidate("liquidity-quality", "v0.1", "低换手+低波+均线低位", ["low_turnover10", "low_vol20", "price_below_ma60"], [0.4, 0.3, 0.3]),
    ]


FACTOR_FAMILIES = {
    "size": ["size20", "size40", "size60"],
    "low-vol": ["low_vol10", "low_vol20", "low_vol40"],
    "reversal": ["reversal5", "reversal10", "reversal20"],
    "momentum-quality": ["momentum_quality10", "momentum_quality20", "momentum_quality40"],
    "liquidity-flow": ["low_turnover5", "low_turnover10", "low_turnover20"],
    "price-location": ["price_below_ma20", "price_below_ma60"],
}


def _candidate_family(factors):
    tags = []
    for family, names in FACTOR_FAMILIES.items():
        if any(f in names for f in factors):
            tags.append(family)
    if tags == ["size"]:
        return "small-cap-size"
    if len(tags) == 1:
        return tags[0]
    return "-".join(tags[:3])


def _version(prefix, i):
    return f"{prefix}.{i:03d}"


def grid_candidates(limit=None):
    """Deterministic first grid for stage 1.2.

    It expands across factor choices, simple two/three-factor blends, holding
    breadth and rebalance frequency. This is still enumeration, not NSGA-II.
    """
    candidates = []
    top_ns = [20, 25, 40]
    rebalances = [10, 20, 40]

    base_factors = [name for names in FACTOR_FAMILIES.values() for name in names]
    i = 1
    for top_n in top_ns:
        for rebal in rebalances:
            for factor in base_factors:
                candidates.append(Candidate(
                    _candidate_family([factor]), _version("grid", i),
                    f"{factor} top{top_n} reb{rebal}",
                    [factor], [1.0], top_n=top_n, rebalance_days=rebal,
                    leverage=1.0 if factor != "size60" else 1.25,
                ))
                i += 1

    blend_specs = [
        (("size60", "low_vol20"), (0.5, 0.5)),
        (("size60", "reversal20"), (0.5, 0.5)),
        (("size60", "low_turnover10"), (0.5, 0.5)),
        (("low_vol20", "reversal20"), (0.5, 0.5)),
        (("low_turnover10", "low_vol20"), (0.5, 0.5)),
        (("low_turnover10", "price_below_ma60"), (0.5, 0.5)),
        (("size60", "low_vol20", "reversal20"), (0.4, 0.3, 0.3)),
        (("low_turnover10", "low_vol20", "price_below_ma60"), (0.4, 0.3, 0.3)),
    ]
    for factors, weights in blend_specs:
        for top_n in top_ns:
            for rebal in rebalances:
                candidates.append(Candidate(
                    _candidate_family(factors), _version("blend", i),
                    f"{'+'.join(factors)} top{top_n} reb{rebal}",
                    list(factors), list(weights), top_n=top_n,
                    rebalance_days=rebal, leverage=1.0,
                ))
                i += 1

    return candidates[:limit] if limit else candidates
