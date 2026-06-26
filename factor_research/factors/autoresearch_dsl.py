"""Runtime factor for controlled AutoResearch JSON AST candidates.

This is the only execution surface for AutoResearch DSL. Agents never write
Python factor code; validated ASTs are interpreted here and then passed through
the existing L0/L1/L2/L3 validation lines.
"""
from __future__ import annotations

import importlib
import json
from typing import Any

import numpy as np
import pandas as pd

from factors.utils import mad_clip, safe_zscore


_FACTOR_CALLS = {
    "momentum": ("factors.momentum", "mom_n", {"window": "n"}),
    "volume_ratio": ("factors.momentum", "vol_ratio", {"window": "short"}),
    "volatility": ("factors.momentum", "volatility", {"window": "n"}),
    "illiquidity": ("factors.momentum", "illiquidity", {"window": "n"}),
    "roe": ("factors.fundamental", "roe", {}),
    "net_profit_yoy": ("factors.fundamental", "net_profit_yoy", {}),
    "revenue_yoy": ("factors.fundamental", "revenue_yoy", {}),
    "bp_proxy": ("factors.fundamental", "bp_proxy", {}),
    "ep_proxy": ("factors.fundamental", "ep_proxy", {}),
    # 独立数据族隔离岛(LOOP_ENGINEERING.md #5):股东行为 + 资金流,与价量簇正交
    "holder_count_chg": ("factors.shareholder", "holder_count_chg", {"window": "window"}),
    "holdertrade_net": ("factors.shareholder", "holdertrade_net", {"window": "window"}),
    "large_order_net_ratio": ("factors.capital_flow", "large_order_net_ratio", {"window": "window"}),
    # 北向资金正交族(与 factory.autoresearch.registry.ALLOWED_FACTORS 同步)
    "northbound_accumulation": ("factors.northbound", "northbound_accumulation", {"window": "window"}),
    "northbound_hold_level": ("factors.northbound", "northbound_hold_level", {}),
    "northbound_flow_strength": ("factors.northbound", "northbound_flow_strength", {"window": "window"}),
    "alpha_001": ("factors.alpha101", "alpha_001", {}),
    "alpha_002": ("factors.alpha101", "alpha_002", {}),
    "alpha_003": ("factors.alpha101", "alpha_003", {}),
    "alpha_005": ("factors.alpha101", "alpha_005", {}),
    "alpha_006": ("factors.alpha101", "alpha_006", {}),
    "alpha_008": ("factors.alpha101", "alpha_008", {}),
    "alpha_009": ("factors.alpha101", "alpha_009", {}),
    "alpha_012": ("factors.alpha101", "alpha_012", {}),
    "alpha_013": ("factors.alpha101", "alpha_013", {}),
    "alpha_014": ("factors.alpha101", "alpha_014", {}),
    "alpha_015": ("factors.alpha101", "alpha_015", {}),
    "alpha_017": ("factors.alpha101", "alpha_017", {}),
    "alpha_018": ("factors.alpha101", "alpha_018", {}),
    "alpha_019": ("factors.alpha101", "alpha_019", {}),
    "alpha_020": ("factors.alpha101", "alpha_020", {}),
    "alpha_021": ("factors.alpha101", "alpha_021", {}),
    "alpha_022": ("factors.alpha101", "alpha_022", {}),
    "alpha_023": ("factors.alpha101", "alpha_023", {}),
    "alpha_024": ("factors.alpha101", "alpha_024", {}),
    "alpha_025": ("factors.alpha101", "alpha_025", {}),
    "alpha_028": ("factors.alpha101", "alpha_028", {}),
    "alpha_030": ("factors.alpha101", "alpha_030", {}),
    "alpha_032": ("factors.alpha101", "alpha_032", {}),
    "alpha_033": ("factors.alpha101", "alpha_033", {}),
    "alpha_034": ("factors.alpha101", "alpha_034", {}),
    "alpha_037": ("factors.alpha101", "alpha_037", {}),
    "alpha_038": ("factors.alpha101", "alpha_038", {}),
    "alpha_040": ("factors.alpha101", "alpha_040", {}),
    "alpha_044": ("factors.alpha101", "alpha_044", {}),
    "alpha_049": ("factors.alpha101", "alpha_049", {}),
    "alpha_050": ("factors.alpha101", "alpha_050", {}),
    "alpha_055": ("factors.alpha101", "alpha_055", {}),
}


def _call_factor(name: str, close: pd.DataFrame, volume: pd.DataFrame | None, params: dict) -> pd.DataFrame:
    if name not in _FACTOR_CALLS:
        raise ValueError(f"unknown AutoResearch DSL factor: {name}")
    module_name, fn_name, param_map = _FACTOR_CALLS[name]
    fn = getattr(importlib.import_module(module_name), fn_name)
    mapped = {target: params[source] for source, target in param_map.items() if source in params}

    if name.startswith("alpha_"):
        return fn(close, volume, **mapped)
    if name in {"volume_ratio"}:
        if volume is None:
            raise ValueError(f"{name} requires volume")
        if "long" not in mapped:
            mapped["long"] = max(int(mapped.get("short", 5)) * 4, int(mapped.get("short", 5)) + 1)
        return fn(volume, **mapped)
    if name == "illiquidity":
        if volume is None:
            raise ValueError("illiquidity requires volume")
        return fn(close, volume, **mapped)
    return fn(close, **mapped)


def _apply_transform(values: pd.DataFrame, op: str, close: pd.DataFrame | None = None) -> pd.DataFrame:
    if op == "mad_clip":
        return mad_clip(values)
    if op == "zscore":
        return safe_zscore(values)
    if op == "rank":
        return values.rank(axis=1, pct=True)
    if op == "neg":
        return -values
    if op == "log1p":
        return np.log1p(values.clip(lower=-0.999999))
    if op == "rolling_mean":
        return values.rolling(20).mean()
    if op == "rolling_std":
        return values.rolling(20).std()
    if op == "regime_gate":
        if close is None:
            raise ValueError("regime_gate requires close price panel")
        mkt_ret = close.pct_change(fill_method=None).fillna(0.0).mean(axis=1)
        mkt_idx = (1 + mkt_ret).cumprod()
        mkt_ma = mkt_idx.rolling(16).mean()
        bull_mask = mkt_idx > mkt_ma

        out = values.copy()
        common_idx = out.index.intersection(bull_mask.index)
        bear_dates = common_idx[~bull_mask.loc[common_idx]]
        out.loc[bear_dates] = 0.0
        return out
    raise ValueError(f"unknown AutoResearch DSL transform: {op}")


# 因子面板搜索内 memo:L0(算 IC)与岛屿适应度(novelty/corr/turnover)对同一
# 候选各算一次全市场面板(5207×2000),memo 让二者共享一次计算(~2× 加速)。
# key 含**带符号** ast 哈希(F 与 -F 面板相反,绝不可共享)+ id(close)
# (防数据湖同日重写的陈旧命中:重载 = 新对象 = 新 id)。搜索起点 clear。
import hashlib as _hashlib

_PANEL_CACHE: dict = {}
_PANEL_ORDER: list = []
_PANEL_CACHE_MAX = 6


def clear_factor_cache() -> None:
    """搜索起点清空面板 memo(隔离不同 run / 不同数据口径)。"""
    _PANEL_CACHE.clear()
    _PANEL_ORDER.clear()


def _panel_key(ast: dict, close, volume):
    body = {k: v for k, v in ast.items() if k != "thesis"}  # direction 参与=带符号
    h = _hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return (h, id(close), volume is not None)


def compute_dsl_factor(
    close: pd.DataFrame,
    volume: pd.DataFrame | None = None,
    *,
    ast: dict[str, Any],
) -> pd.DataFrame:
    """Compute a validated AutoResearch linear_combo AST(搜索内 memo 化)。"""
    if ast.get("type") != "linear_combo":
        raise ValueError(f"unsupported AutoResearch AST type: {ast.get('type')}")

    key = _panel_key(ast, close, volume)
    cached = _PANEL_CACHE.get(key)
    if cached is not None:
        return cached

    out = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for term in ast.get("terms", []):
        values = _call_factor(term["factor"], close, volume, term.get("params", {}))
        values = values.reindex(index=close.index, columns=close.columns)
        for op in term.get("transforms", []):
            values = _apply_transform(values, op, close=close)
        out = out.add(float(term.get("weight", 1.0)) * values, fill_value=0.0)

    if ast.get("direction") == "negative":
        out = -out
    out = out.replace([np.inf, -np.inf], np.nan)

    _PANEL_CACHE[key] = out
    _PANEL_ORDER.append(key)
    if len(_PANEL_ORDER) > _PANEL_CACHE_MAX:
        _PANEL_CACHE.pop(_PANEL_ORDER.pop(0), None)
    return out
