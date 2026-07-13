"""Whitelists for the Auto Factor Research DSL."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FactorSpec:
    name: str
    params: dict[str, tuple[int | float, int | float]] = field(default_factory=dict)
    data_dependencies: tuple[str, ...] = ()


# 搜索白名单全部由 @register_factor(searchable=True) 注入;本表不再手写因子条目。
# setdefault:若未来需临时覆盖某因子 params,可在此预置后 discover 不会覆盖。
ALLOWED_FACTORS: dict[str, FactorSpec] = {}

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
