"""Volatility factor — rolling standard deviation of returns.

Positive = higher volatility (risk premium / attention proxy in A股).
Use .neg() to get low-volatility factor.
"""
import pandas as pd

from factors.alpha.base import Factor, FactorData


class Volatility(Factor):
    """N-day rolling return volatility.

    Parameters
    ----------
    window : int
        Lookback period (default 20).
    """

    def __init__(self, window: int = 20):
        self.window = window

    def compute(self, data: FactorData) -> pd.DataFrame:
        ret = data.close.pct_change(fill_method=None)
        return ret.rolling(self.window).std()
