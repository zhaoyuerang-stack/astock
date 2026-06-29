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
    "alpha_001": FactorSpec("alpha_001", {}, ("price/close", "price/volume")),
    "alpha_002": FactorSpec("alpha_002", {}, ("price/close", "price/volume")),
    "alpha_003": FactorSpec("alpha_003", {}, ("price/close", "price/volume")),
    "alpha_005": FactorSpec("alpha_005", {}, ("price/close",)),
    "alpha_006": FactorSpec("alpha_006", {}, ("price/close", "price/volume")),
    "alpha_008": FactorSpec("alpha_008", {}, ("price/close",)),
    "alpha_009": FactorSpec("alpha_009", {}, ("price/close",)),
    "alpha_012": FactorSpec("alpha_012", {}, ("price/close", "price/volume")),
    "alpha_013": FactorSpec("alpha_013", {}, ("price/close", "price/volume")),
    "alpha_014": FactorSpec("alpha_014", {}, ("price/close", "price/volume")),
    "alpha_015": FactorSpec("alpha_015", {}, ("price/close", "price/volume")),
    "alpha_017": FactorSpec("alpha_017", {}, ("price/close",)),
    "alpha_018": FactorSpec("alpha_018", {}, ("price/close",)),
    "alpha_019": FactorSpec("alpha_019", {}, ("price/close",)),
    "alpha_020": FactorSpec("alpha_020", {}, ("price/close",)),
    "alpha_021": FactorSpec("alpha_021", {}, ("price/close",)),
    "alpha_022": FactorSpec("alpha_022", {}, ("price/close",)),
    "alpha_023": FactorSpec("alpha_023", {}, ("price/close",)),
    "alpha_024": FactorSpec("alpha_024", {}, ("price/close",)),
    "alpha_025": FactorSpec("alpha_025", {}, ("price/close",)),
    "alpha_028": FactorSpec("alpha_028", {}, ("price/close", "price/volume")),
    "alpha_030": FactorSpec("alpha_030", {}, ("price/close", "price/volume")),
    "alpha_032": FactorSpec("alpha_032", {}, ("price/close",)),
    "alpha_033": FactorSpec("alpha_033", {}, ("price/close",)),
    "alpha_034": FactorSpec("alpha_034", {}, ("price/close",)),
    "alpha_037": FactorSpec("alpha_037", {}, ("price/close",)),
    "alpha_038": FactorSpec("alpha_038", {}, ("price/close",)),
    "alpha_040": FactorSpec("alpha_040", {}, ("price/close", "price/volume")),
    "alpha_044": FactorSpec("alpha_044", {}, ("price/close", "price/volume")),
    "alpha_049": FactorSpec("alpha_049", {}, ("price/close",)),
    "alpha_050": FactorSpec("alpha_050", {}, ("price/close", "price/volume")),
    "alpha_055": FactorSpec("alpha_055", {}, ("price/close", "price/volume")),
    # 独立数据族隔离岛(LOOP_ENGINEERING.md #5):股东行为 + 资金流,与价量簇正交
    "holder_count_chg": FactorSpec("holder_count_chg", {"window": (40, 240)}, ("holder/holdernumber",)),
    "holdertrade_net": FactorSpec("holdertrade_net", {"window": (40, 250)}, ("holder/holdertrade",)),
    "large_order_net_ratio": FactorSpec("large_order_net_ratio", {"window": (3, 60)}, ("moneyflow",)),
    # 北向资金(沪深股通持仓):L0 验证与 size/流动性正交(残差 IC 不塌、与小盘 corr≈0),
    # 给搜索空间加上跳出小盘簇的正交维度。
    "northbound_accumulation": FactorSpec("northbound_accumulation", {"window": (5, 120)}, ("capital/northbound",)),
    "northbound_hold_level": FactorSpec("northbound_hold_level", {}, ("capital/northbound",)),
    "northbound_flow_strength": FactorSpec("northbound_flow_strength", {"window": (3, 20)}, ("capital/northbound",)),
}

# ── @register_factor 自动接线: 只有显式 searchable=True 的因子才进搜索白名单 ──
# "工厂搜不搜某因子"是研究判断(扩搜索宇宙改变确定性搜索行为),故 opt-in 不自动。
# 手工条目优先(setdefault);单向依赖合规 factory→factors。
from factors.registry import discover as _discover_factors  # noqa: E402

for _name, _rec in _discover_factors().items():
    if _rec.searchable:
        ALLOWED_FACTORS.setdefault(_name, FactorSpec(_name, dict(_rec.params), _rec.data))

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
