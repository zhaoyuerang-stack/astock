"""价格行为因子 — 动量 / 均线偏离 / 波动率(非流动性见 factors.liquidity)。

诚实命名:原 factors.momentum 混装 volatility/illiquidity/量比,现拆出价行为族。
``factors.momentum`` 仍 re-export 本模块以保向后兼容。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factors.registry import register_factor


@register_factor(
    "momentum",
    params={"window": (3, 252)},
    data=("price/close",),
    input="close",
    arg_map={"window": "n"},
    searchable=True,
)
def mom_n(close: pd.DataFrame, n: int, skip: int = 0) -> pd.DataFrame:
    """N日动量，可跳过最近 skip 日（规避短反转）。"""
    if skip > 0:
        return close.shift(skip) / close.shift(n + skip) - 1
    return close / close.shift(n) - 1


@register_factor(
    "price_to_ma",
    params={"window": (5, 252)},
    data=("price/close",),
    input="close",
    arg_map={"window": "n"},
    searchable=False,  # 工厂网格有,但 DSL 白名单未开;保持 opt-in 纪律
)
def price_to_ma(close: pd.DataFrame, n: int) -> pd.DataFrame:
    """价格偏离均线程度 = close/MA(n) - 1。"""
    return close / close.rolling(n).mean() - 1


@register_factor(
    "volatility",
    params={"window": (5, 252)},
    data=("price/close",),
    input="close",
    arg_map={"window": "n"},
    searchable=True,
)
def volatility(close: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """N日收益率波动率(年化)。"""
    ret = close.pct_change(fill_method=None)
    return ret.rolling(n).std() * np.sqrt(252)
