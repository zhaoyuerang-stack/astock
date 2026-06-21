"""Spec 驱动的 canonical 策略构建器(Task 6)。

同一个 ExecutableStrategySpec 必须生成同一 factor / timing / weights / Signal。
研究组合编排(strategy_runners)与生产日信号(run_daily)共用此入口,杜绝公式复制。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.engine import PricePanel, Signal
from core.strategy_spec import ExecutableStrategySpec
from strategies.catalog import (
    resolve_factor_builder,
    resolve_policy_builder,
    resolve_timing_builder,
)
from strategies.small_cap import build_rebalance_weights


@dataclass(frozen=True)
class ExecutableStrategy:
    factor: pd.DataFrame
    timing: pd.Series
    scheduled_weights: dict
    signal: Signal
    spec_hash: str
    diagnostics: dict


def build_executable_strategy(spec: ExecutableStrategySpec, prices: PricePanel) -> ExecutableStrategy:
    """从 spec + 价格面板构建可执行策略(因子→择时→政策过滤→调仓权重→Signal)。"""
    spec.validate()

    factor_builder = resolve_factor_builder(spec.factor["type"])
    timing_builder = resolve_timing_builder(spec.timing["type"])
    policy_builder = resolve_policy_builder(spec.policy.get("veto", "none"))

    factor = factor_builder(prices, spec.factor)
    timing, timing_diag = timing_builder(prices, spec.timing)
    veto_factor, veto_q = policy_builder(prices, spec.policy)

    weights = build_rebalance_weights(
        factor,
        prices.close,
        top_n=int(spec.selection["top_n"]),
        rebalance_days=int(spec.selection["rebalance_days"]),
        veto_factor=veto_factor,
        veto_q=veto_q,
    )

    signal = Signal(
        decision_weights=weights,
        timing=timing,
        family=spec.family,
        version=spec.version,
        exposure_cap=float(spec.timing.get("cap", 1.0)),
        execution_timing=spec.execution["fill"],
    )

    return ExecutableStrategy(
        factor=factor,
        timing=timing,
        scheduled_weights=weights,
        signal=signal,
        spec_hash=spec.spec_hash,
        diagnostics={
            "timing": timing_diag,
            "veto_factor": veto_factor,
            "veto_q": veto_q,
        },
    )
