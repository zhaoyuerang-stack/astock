"""Backward-compatible factor composer wrappers.

New code should import from ``engine.factor_composer`` and
``engine.signal_factory``.
"""
from __future__ import annotations

import pandas as pd

from engine.factor_composer import (
    equal_weight_factor,
    factor_corr_matrix,
    ic_weight_factor,
    pca_factor_composite,
)
from engine.signal_factory import factor_to_signal


def equal_weight(factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return equal_weight_factor(factors)


def ic_weight(
    factors: dict[str, pd.DataFrame],
    forward_ret: pd.DataFrame,
    ic_window: int = 12,
) -> pd.DataFrame:
    return ic_weight_factor(factors, forward_ret, ic_window)


def pca_composite(
    factors: dict[str, pd.DataFrame],
    n_components: int = 1,
) -> pd.DataFrame:
    return pca_factor_composite(factors, n_components)


def to_signal(
    factor: pd.DataFrame,
    top_n: int = 25,
    direction: int = 1,
    rebalance_freq: str = "20D",
    timing: pd.Series | None = None,
    family: str = "",
    version: str = "",
):
    return factor_to_signal(
        factor,
        top_n=top_n,
        direction=direction,
        rebalance_freq=rebalance_freq,
        timing=timing,
        family=family,
        version=version,
    )
