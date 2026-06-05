"""Portfolio construction utilities.

This module provides:
- ``to_signal()`` – bridge factor panels to ``core.engine.Signal``
- ``performance_metrics()`` – metrics from a return series

Deprecated
----------
- ``calc_portfolio_return()`` is deprecated.  For portfolio backtests use
  ``core.engine.BacktestEngine.run()`` which unifies costs, timing, leverage,
  and financing in a single path.
- ``top_n_portfolio()`` is deprecated.  Use ``core.engine.Signal(factor=..., top_n=...)``
  which calls ``BacktestEngine._factor_to_weights()`` internally.
"""
import pandas as pd
import numpy as np


def performance_metrics(port_ret: pd.Series, rf: float = 0.02, fmt: bool = False) -> dict:
    """Performance summary.

    Parameters
    ----------
    port_ret : pd.Series
        Daily portfolio returns.
    rf : float
        Risk-free rate (annual).
    fmt : bool
        If True, return formatted strings (legacy behaviour).
        If False (default), return raw floats for programmatic use.
    """
    ret = port_ret.dropna()
    annual_ret = ret.mean() * 252
    annual_vol = ret.std() * np.sqrt(252)
    sharpe = (annual_ret - rf) / annual_vol if annual_vol > 0 else np.nan
    cum = (1 + ret).cumprod()
    maxdd = (cum / cum.cummax() - 1).min()
    calmar = annual_ret / abs(maxdd) if maxdd != 0 else np.nan
    if fmt:
        return {
            "年化收益": f"{annual_ret:.2%}",
            "年化波动": f"{annual_vol:.2%}",
            "夏普比率": f"{sharpe:.2f}",
            "最大回撤": f"{maxdd:.2%}",
            "卡玛比率": f"{calmar:.2f}",
        }
    return {
        "annual": annual_ret,
        "vol": annual_vol,
        "sharpe": sharpe,
        "maxdd": maxdd,
        "calmar": calmar,
    }


def to_signal(factor: pd.DataFrame, n: int = 100, direction: int = 1,
              rebalance_freq: str = "W", family: str = "", version: str = ""):
    """Wrap a factor panel into a ``core.engine.Signal`` (factor mode).

    The engine will convert the factor to top-n weights internally.
    """
    from core.engine import Signal
    return Signal(
        factor=factor,
        top_n=n,
        direction=direction,
        rebalance_freq=rebalance_freq,
        family=family,
        version=version,
    )
