"""流动性 / 成交相关因子 — Amihud illiquidity、量比、换手。

与 factors.price_action(价行为)分离;原 factors.momentum 混装已拆。
``factors.momentum`` 仍 re-export 本模块以保向后兼容。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factors.registry import register_factor


def turnover_mean(amount: pd.DataFrame, capital: pd.DataFrame, n: int) -> pd.DataFrame:
    """N日平均换手率 = 成交额/流通市值(非 DSL 单面板因子,不进 register)。"""
    turn = amount / capital
    return turn.rolling(n).mean()


@register_factor(
    "volume_ratio",
    params={"window": (3, 120)},
    data=("price/volume",),
    input="volume",
    arg_map={"window": "short"},
    searchable=True,
)
def vol_ratio(volume: pd.DataFrame, short: int = 5, long: int = 20) -> pd.DataFrame:
    """量比 = 近 short 日均量 / 近 long 日均量。"""
    return volume.rolling(short).mean() / volume.rolling(long).mean()


@register_factor(
    "illiquidity",
    params={"window": (5, 120)},
    data=("price/close", "price/volume", "price/amount"),
    input="close",
    arg_map={"window": "n"},
    searchable=True,
)
def illiquidity(close: pd.DataFrame, volume: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Amihud 非流动性 = mean(|ret| / amount)，与 `factors.alpha.builtins.illiq.AmihudIlliq` 对齐。

    正式 Amihud(2002) 分母是成交额 amount，不是成交量 volume。
    AutoResearch DSL 表面只有 close/volume 时，用 amount ≈ volume × close 代理
    （在 amount = volume×price 时与 OO 版同构；截面排序下常数单位差可消）。

    历史错误口径曾写 mean(|ret|/volume)，等价于 Amihud×价格水平，会把价格因子
    混进「illiquidity」搜索语义——已纠正，勿回退。

    DSL 执行面特殊分派(close, volume);catalog 自动 builder 仅单 input,策略侧
    仍用手写 amihud_illiquidity builder。
    """
    ret = close.pct_change(fill_method=None).abs()
    amount = volume.astype(float) * close.astype(float)
    daily = ret / (amount.replace(0, np.nan) + 1.0)
    return daily.rolling(n).mean()
