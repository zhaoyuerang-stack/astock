"""Whitelists for the Auto Factor Research DSL."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FactorSpec:
    name: str
    params: dict[str, tuple[int | float, int | float]] = field(default_factory=dict)
    data_dependencies: tuple[str, ...] = ()


ALLOWED_FACTORS: dict[str, FactorSpec] = {
    "momentum": FactorSpec("momentum", {"window": (3, 252)}, ("price/close",)),
    "volume_ratio": FactorSpec("volume_ratio", {"window": (3, 120)}, ("price/volume",)),
    "volatility": FactorSpec("volatility", {"window": (5, 252)}, ("price/close",)),
    "illiquidity": FactorSpec("illiquidity", {"window": (5, 120)}, ("price/close", "price/volume")),
    "roe": FactorSpec("roe", {}, ("fundamental/roe",)),
    "net_profit_yoy": FactorSpec("net_profit_yoy", {}, ("fundamental/net_profit_yoy",)),
    "revenue_yoy": FactorSpec("revenue_yoy", {}, ("fundamental/revenue_yoy",)),
    "bp_proxy": FactorSpec("bp_proxy", {}, ("price/close", "fundamental/bps")),
    "ep_proxy": FactorSpec("ep_proxy", {}, ("price/close", "fundamental/eps_ttm")),
}

ALLOWED_TRANSFORMS = {
    "mad_clip",
    "zscore",
    "rank",
    "neg",
    "log1p",
    "rolling_mean",
    "rolling_std",
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
