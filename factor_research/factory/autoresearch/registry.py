"""Whitelists for the Auto Factor Research DSL."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FactorSpec:
    name: str
    params: dict[str, tuple[int | float, int | float]] = field(default_factory=dict)
    data_dependencies: tuple[str, ...] = ()


# 手工条目仅保留「尚未 @register_factor 或需覆盖 params」的因子。
# momentum/fundamental/northbound/alpha101 等已由 factors.registry discover 自动注入
# (searchable=True);setdefault → 装饰器优先,本表只补缺/覆盖。
ALLOWED_FACTORS: dict[str, FactorSpec] = {
    # 股东/资金流:register 的 window 范围与搜索宇宙刻意不同 → 手工覆盖保留
    "holder_count_chg": FactorSpec(
        "holder_count_chg", {"window": (40, 240)}, ("holder/holdernumber",)
    ),
    "holdertrade_net": FactorSpec(
        "holdertrade_net", {"window": (40, 250)}, ("holder/holdertrade",)
    ),
    "large_order_net_ratio": FactorSpec(
        "large_order_net_ratio", {"window": (3, 60)}, ("moneyflow",)
    ),
}

# ── @register_factor 自动接线: 只有显式 searchable=True 的因子才进搜索白名单 ──
# "工厂搜不搜某因子"是研究判断(扩搜索宇宙改变确定性搜索行为),故 opt-in 不自动。
# 手工条目优先(setdefault);单向依赖合规 factory→factors。
from factors.registry import discover as _discover_factors  # noqa: E402

for _name, _rec in _discover_factors().items():
    if _rec.searchable:
        ALLOWED_FACTORS.setdefault(
            _name, FactorSpec(_name, dict(_rec.params), _rec.data)
        )

ALLOWED_TRANSFORMS = {
    "mad_clip",
    "zscore",
    "rank",
    "neg",
    "log1p",
    "rolling_mean",
    "rolling_std",
    "regime_gate",
    "fundamental_veto",
    "salience_veto",
    "error_feedback_correction",
}

ALLOWED_NEUTRALIZE = {"industry", "size"}
ALLOWED_DIRECTIONS = {"positive", "negative"}
ALLOWED_TYPES = {"linear_combo"}

FORBIDDEN_TOKENS = (
    "future",
    "forward_return",
    "label",
    "target",
    "next_",
    "tomorrow",
)


def looks_forbidden(value: Any) -> bool:
    text = str(value).lower()
    return any(token in text for token in FORBIDDEN_TOKENS)
