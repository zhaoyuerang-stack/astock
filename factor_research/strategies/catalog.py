"""Canonical 策略组件目录(Task 6)。

把 factor / timing / policy 的真实实现集中为确定性映射,供 spec 驱动的
build_executable_strategy 解析。未知类型一律抛 UnsupportedStrategyComponent,
绝不静默 fallback —— 杜绝「拼错 type 却照常出信号」的隐性漂移。

所有 builder 都委托既有 canonical 实现(factors.* / strategies.small_cap),
本模块只做「spec 字段 → 既有函数」的解析,不复制任何公式。
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from core.engine import PricePanel


class UnsupportedStrategyComponent(ValueError):
    """spec 引用了目录中不存在的组件类型。"""


# ────────────────────────── factor builders ──────────────────────────
# 签名: (prices: PricePanel, params: dict) -> factor DataFrame(date × code)

def build_amihud_illiquidity(prices: PricePanel, params: dict) -> pd.DataFrame:
    """Amihud |ret|/amount 非流动性,MAD clip → zscore → shift(防未来)。

    与 run_daily 生产表达式逐位一致: AmihudIlliq(window).mad_clip(c).zscore().shift(s)。
    """
    import factors.alpha.transforms  # noqa: F401 —— 副作用注册 mad_clip/zscore transform
    from factors.alpha.base import FactorData
    from factors.alpha.builtins.illiq import AmihudIlliq

    window = int(params.get("window", 20))
    shift = int(params.get("shift", 1))
    clip = float(params.get("mad_clip", 5))
    data = FactorData(close=prices.close, volume=prices.volume, amount=prices.amount)
    expr = AmihudIlliq(window=window).mad_clip(clip).zscore().shift(shift)
    return expr.compute(data)


def build_small_cap_amount(prices: PricePanel, params: dict) -> pd.DataFrame:
    """小盘规模代理: -ln(avg amount),zscore。"""
    from factors.small_cap import small_cap_factor

    return small_cap_factor(prices.amount, window=int(params.get("window", 60)))


# ────────────────────────── timing builders ──────────────────────────
# 签名: (prices, params) -> (exposure: pd.Series, diagnostics: dict)

def build_pure_trend_band(prices: PricePanel, params: dict):
    """PureTrend Band 动态择时: exposure = clip(1 + dist*8, 0, cap) × I(dist>0),shift(1)。

    生产用当日 dist 决定次日持仓 ⇒ 回测里 exposure 须 shift(1),与二值 timing 的
    shift(1) 防未来一致。
    """
    from factors.small_cap import small_cap_timing

    ma = int(params.get("ma", 16))
    cap = float(params.get("cap", 1.5))
    _, _, dist = small_cap_timing(prices.close, prices.amount, ma_window=ma)
    dc = dist.clip(-0.5, 0.5)
    band = (1.0 + dc * 8.0).clip(0.0, cap)
    exposure = band.where(dc > 0, 0.0).shift(1).fillna(0.0)
    return exposure, {"type": "pure_trend_band", "ma": ma, "cap": cap}


def build_ma_trend(prices: PricePanel, params: dict):
    """二值 MA 趋势择时(small-cap nav > MA)。"""
    from factors.small_cap import small_cap_timing

    ma = int(params.get("ma", 16))
    timing, _, _ = small_cap_timing(prices.close, prices.amount, ma_window=ma)
    return timing.astype(float), {"type": "ma_trend", "ma": ma}


# ────────────────────────── policy builders ──────────────────────────
# 签名: (prices, params) -> (veto_factor: pd.DataFrame | None, veto_q: float)
# veto 在 build_rebalance_weights 内对候选池过滤,不预改 factor —— 保持真实语义。

def apply_no_policy(prices: PricePanel, params: dict):
    return None, 0.0


def apply_salience_veto(prices: PricePanel, params: dict):
    from factors.veto import salience_covariance_veto

    return salience_covariance_veto(prices.close).shift(1), float(params.get("veto_q", 0.30))


FACTOR_BUILDERS: dict[str, Callable] = {
    "amihud_illiquidity": build_amihud_illiquidity,
    "small_cap_amount": build_small_cap_amount,
}

TIMING_BUILDERS: dict[str, Callable] = {
    "pure_trend_band": build_pure_trend_band,
    "ma_trend": build_ma_trend,
}

POLICY_BUILDERS: dict[str, Callable] = {
    "none": apply_no_policy,
    "salience_covariance": apply_salience_veto,
}


def resolve_factor_builder(name: str) -> Callable:
    try:
        return FACTOR_BUILDERS[name]
    except KeyError:
        raise UnsupportedStrategyComponent(f"未知 factor type={name!r}(可选: {sorted(FACTOR_BUILDERS)})")


def resolve_timing_builder(name: str) -> Callable:
    try:
        return TIMING_BUILDERS[name]
    except KeyError:
        raise UnsupportedStrategyComponent(f"未知 timing type={name!r}(可选: {sorted(TIMING_BUILDERS)})")


def resolve_policy_builder(name: str) -> Callable:
    try:
        return POLICY_BUILDERS[name]
    except KeyError:
        raise UnsupportedStrategyComponent(f"未知 policy veto={name!r}(可选: {sorted(POLICY_BUILDERS)})")
