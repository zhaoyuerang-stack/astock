"""Runtime factor for controlled AutoResearch JSON AST candidates.

This is the only execution surface for AutoResearch DSL. Agents never write
Python factor code; validated ASTs are interpreted here and then passed through
the existing L0/L1/L2/L3 validation lines.
"""
from __future__ import annotations

import importlib
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
}


def _call_factor(name: str, close: pd.DataFrame, volume: pd.DataFrame | None, params: dict) -> pd.DataFrame:
    if name not in _FACTOR_CALLS:
        raise ValueError(f"unknown AutoResearch DSL factor: {name}")
    module_name, fn_name, param_map = _FACTOR_CALLS[name]
    fn = getattr(importlib.import_module(module_name), fn_name)
    mapped = {target: params[source] for source, target in param_map.items() if source in params}

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


def _apply_transform(values: pd.DataFrame, op: str) -> pd.DataFrame:
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
    raise ValueError(f"unknown AutoResearch DSL transform: {op}")


def compute_dsl_factor(
    close: pd.DataFrame,
    volume: pd.DataFrame | None = None,
    *,
    ast: dict[str, Any],
) -> pd.DataFrame:
    """Compute a validated AutoResearch linear_combo AST."""
    if ast.get("type") != "linear_combo":
        raise ValueError(f"unsupported AutoResearch AST type: {ast.get('type')}")

    out = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for term in ast.get("terms", []):
        values = _call_factor(term["factor"], close, volume, term.get("params", {}))
        values = values.reindex(index=close.index, columns=close.columns)
        for op in term.get("transforms", []):
            values = _apply_transform(values, op)
        out = out.add(float(term.get("weight", 1.0)) * values, fill_value=0.0)

    if ast.get("direction") == "negative":
        out = -out
    return out.replace([np.inf, -np.inf], np.nan)
