"""Performance metrics from a return series."""
import numpy as np
import pandas as pd

TARGET_ANNUAL = 0.35
TARGET_MAXDD = 0.15


def max_drawdown(ret):
    """Maximum drawdown from a return series."""
    if len(ret) == 0:
        return np.nan
    cum = (1 + ret).cumprod()
    return float((cum / cum.cummax() - 1).min())


def metrics(ret):
    """Standard performance metrics dict."""
    if len(ret) < 100:
        return {
            "annual": -1.0,
            "vol": 0.0,
            "sharpe": -1.0,
            "maxdd": -1.0,
            "calmar": 0.0,
            "hit": False,
            "n": len(ret),
        }
    annual = ret.mean() * 252
    vol = ret.std() * np.sqrt(252)
    sharpe = annual / vol if vol > 0 else 0
    cum = (1 + ret).cumprod()
    maxdd = (cum / cum.cummax() - 1).min()
    calmar = annual / abs(maxdd) if maxdd < 0 else 0
    hit = (annual >= TARGET_ANNUAL) and (abs(maxdd) <= TARGET_MAXDD)
    return {
        "annual": annual,
        "vol": vol,
        "sharpe": sharpe,
        "maxdd": maxdd,
        "calmar": calmar,
        "hit": hit,
        "n": len(ret),
    }


def yearly_returns(ret):
    """Annual returns from a daily return series."""
    return ret.groupby(ret.index.year).apply(lambda x: (1 + x).prod() - 1)
