"""Candidate strategy definitions for the stage-1 factory."""
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
        "size60": small_cap_factor(amount, 60),
        "low_vol20": safe_zscore(mad_clip(-ret.rolling(20).std())),
        "reversal20": safe_zscore(mad_clip(-(close / close.shift(20) - 1))),
        "reversal5": safe_zscore(mad_clip(-(close / close.shift(5) - 1))),
        "momentum_quality20": safe_zscore(mad_clip((ret > 0).rolling(20).mean())),
        "low_turnover10": safe_zscore(
            mad_clip(-(amount / (amount.rolling(60).mean() + 1e-6)).rolling(10).mean())
        ),
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
