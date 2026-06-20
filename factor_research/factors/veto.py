"""VetoFilter factors.

These factors are policy inputs for host strategies. They are not standalone
long-only alpha factors and must be evaluated by marginal contribution only.
"""
from __future__ import annotations

import pandas as pd


def _row_pct_rank(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True)


def loser_veto_reversal(
    close: pd.DataFrame,
    *,
    lookback: int = 20,
    vol_window: int = 20,
) -> pd.DataFrame:
    """Score stocks for loser-side veto use.

    Higher is safer. The lowest cross-sectional scores represent persistent
    losers with subdued volatility, the "death bucket" to exclude from a host
    candidate pool. The factor uses only prices up to T and is applied by the
    host strategy with its normal T+1 rebalance mechanics.
    """
    momentum = close.pct_change(lookback, fill_method=None)
    volatility = close.pct_change(fill_method=None).rolling(vol_window).std()
    return 0.75 * _row_pct_rank(momentum) + 0.25 * _row_pct_rank(volatility)


def salience_covariance_veto(
    close: pd.DataFrame,
    *,
    W: int = 20,
    theta: float = 0.1,
    delta: float = 0.7,
) -> pd.DataFrame:
    """Computes faded Salience Covariance (-ST_cov) as a veto factor.

    Higher is safer (less salient / lower bubble risk).
    """
    import numpy as np
    returns = close.pct_change(fill_method=None)
    market_returns = returns.mean(axis=1)

    r_diff = returns.sub(market_returns, axis=0).abs()
    r_sum = returns.abs().add(market_returns.abs(), axis=0) + theta
    salience = r_diff / r_sum

    ranks = {}
    valid_count = pd.DataFrame(0, index=salience.index, columns=salience.columns)
    for j in range(W):
        valid_count += salience.shift(j).notna().astype(int)

    for s in range(W):
        better_count = pd.DataFrame(0, index=salience.index, columns=salience.columns)
        for j in range(W):
            if j == s:
                continue
            better_count += (salience.shift(j) > salience.shift(s)).astype(int)
        ranks[s] = (better_count + 1).where(salience.shift(s).notna())

    denom = delta * (1 - delta ** valid_count) / (1 - delta)

    est_return = pd.DataFrame(0.0, index=returns.index, columns=returns.columns)
    for s in range(W):
        weight_s = (delta ** ranks[s]) / denom
        r_lag = returns.shift(s)
        est_return += weight_s * r_lag.fillna(0.0)

    avg_return = returns.rolling(W).mean()
    st_cov = est_return - avg_return
    return -st_cov

