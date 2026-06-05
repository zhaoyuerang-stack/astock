"""Small-cap size factor and timing signal."""
import numpy as np
import pandas as pd
from factors.utils import safe_zscore, mad_clip


def small_cap_factor(amount, window=60):
    """Small-cap factor: low turnover proxy for market-cap (negative log of avg amount)."""
    return safe_zscore(mad_clip(-np.log(amount.rolling(window).mean() + 1)))


def small_cap_timing(close, amount, ma_window=16):
    """Small-cap regime timing: long when small-cap nav > MA."""
    ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
    small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
    small_nav = (1 + small_idx.fillna(0)).cumprod()
    timing = (small_nav > small_nav.rolling(ma_window).mean()).shift(1, fill_value=False).astype(bool)
    dist = small_nav / small_nav.rolling(ma_window).mean() - 1
    return timing, small_nav, dist
