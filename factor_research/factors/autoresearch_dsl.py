"""Runtime factor for controlled AutoResearch JSON AST candidates.

This is the only execution surface for AutoResearch DSL. Agents never write
Python factor code; validated ASTs are interpreted here and then passed through
the existing L0/L1/L2/L3 validation lines.
"""
from __future__ import annotations

import importlib
import json
from typing import Any
from pathlib import Path

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

# ── @register_factor 自动接线: factors 层登记的因子自动补进 DSL 调用表(手工优先)──
# 同层 factors→factors;新因子 @register_factor 后这里自动出现,无需手改。
from factors.registry import discover as _discover_factors  # noqa: E402

for _name, _rec in _discover_factors().items():
    _FACTOR_CALLS.setdefault(_name, (_rec.fn.__module__, _rec.fn.__name__, dict(_rec.arg_map)))


_BASE_FACTOR_MEM_CACHE: dict = {}
_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_DATA_PATHS = (
    _ROOT / "data_lake" / "price" / "daily_all.parquet",
    _ROOT / "data_lake" / "daily_all.parquet",
)


def _source_data_mtime() -> int:
    for source_path in _SOURCE_DATA_PATHS:
        try:
            if source_path.exists():
                return int(source_path.stat().st_mtime)
        except OSError:
            continue
    return 0


def _get_cache_path(name: str, params: dict) -> Path:
    mtime = _source_data_mtime()
    if not params:
        filename = f"{name}_mt{mtime}.parquet"
    else:
        param_str = "_".join(f"{k}_{v}" for k, v in sorted(params.items()))
        filename = f"{name}_{param_str}_mt{mtime}.parquet"
    base_dir = _ROOT / "data_lake" / "factor_store" / "panels"
    return base_dir / filename

def _call_factor(name: str, close: pd.DataFrame, volume: pd.DataFrame | None, params: dict, cache_mode: str = "disk") -> pd.DataFrame:
    mtime = _source_data_mtime()

    # 1. Check in-memory cache first
    param_key = json.dumps(params, sort_keys=True)
    mem_key = (name, param_key, id(close), mtime)
    if mem_key in _BASE_FACTOR_MEM_CACHE:
        return _BASE_FACTOR_MEM_CACHE[mem_key]

    # 2. Check local parquet cache unless caller requested pure in-memory mode.
    # If cache_mode is 'memory', bypass disk reading completely (Task 1652 test requirement)
    if cache_mode != "memory":
        cache_path = _get_cache_path(name, params)
        if cache_path.exists():
            try:
                cached = pd.read_parquet(cache_path)
                if cached.index.intersection(close.index).empty or cached.columns.intersection(close.columns).empty:
                    raise ValueError("cached factor panel does not overlap active panel")
                # Reindex to ensure strict compatibility with the active close index and columns
                df = cached.reindex(index=close.index, columns=close.columns)
                if not df.notna().to_numpy().any():
                    raise ValueError("cached factor panel has no valid values for active panel")
                _BASE_FACTOR_MEM_CACHE[mem_key] = df
                return df
            except Exception:
                pass

    # 3. Compute factor if not cached
    if name not in _FACTOR_CALLS:
        raise ValueError(f"unknown AutoResearch DSL factor: {name}")
    module_name, fn_name, param_map = _FACTOR_CALLS[name]
    fn = getattr(importlib.import_module(module_name), fn_name)
    mapped = {target: params[source] for source, target in param_map.items() if source in params}

    if name.startswith("alpha_"):
        out = fn(close, volume, **mapped)
    elif name in {"volume_ratio"}:
        if volume is None:
            raise ValueError(f"{name} requires volume")
        if "long" not in mapped:
            mapped["long"] = max(int(mapped.get("short", 5)) * 4, int(mapped.get("short", 5)) + 1)
        out = fn(volume, **mapped)
    elif name == "illiquidity":
        if volume is None:
            raise ValueError("illiquidity requires volume")
        out = fn(close, volume, **mapped)
    else:
        out = fn(close, **mapped)

    # 4. Save to parquet cache
    if cache_mode != "memory":
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            out.to_parquet(cache_path)
        except Exception:
            pass

    _BASE_FACTOR_MEM_CACHE[mem_key] = out
    return out

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
    if op == "fundamental_veto":
        if close is None:
            raise ValueError("fundamental_veto requires close price panel")
        from factors.fundamental import _load_fundamental_cache, _align_to_close
        fund = _load_fundamental_cache()
        roe_panel = _align_to_close(fund["roe"], close)
        npy_panel = _align_to_close(fund["net_profit_yoy"], close)
        # Veto stocks with negative/low ROE (<= 0.0%) or crashing earnings growth (< -30%)
        veto_mask = (roe_panel <= 0.0) | (npy_panel < -30.0)
        out = values.copy()
        out[veto_mask] = np.nan
        return out
    if op == "salience_veto":
        if close is None:
            raise ValueError("salience_veto requires close price panel")
        # Overheating proxy: 5-day return volatility divided by 60-day return volatility
        ret = close.pct_change(fill_method=None)
        vol_5d = ret.rolling(5).std()
        vol_60d = ret.rolling(60).std()
        vol_ratio = vol_5d / (vol_60d + 1e-10)
        # Veto top 5% most volatile stocks in the cross-section
        overheated_mask = vol_ratio.rank(axis=1, pct=True) > 0.95
        out = values.copy()
        out[overheated_mask] = np.nan
        return out
    if op == "error_feedback_correction":
        if close is None:
            raise ValueError("error_feedback_correction requires close price panel")
        # 1. Calculate stock returns
        ret = close.pct_change(fill_method=None)
        # 2. Identify factor's historical signals (we shift values by 1 day to align with holding period)
        # For simplicity, we assume values > 0 are buy signals
        signal_held = (values.shift(1) > 0).astype(float)
        # 3. Calculate realized losses: signal_held * min(0, return)
        realized_loss = signal_held * ret.clip(upper=0.0)
        # 4. Accumulate rolling losses over the past 20 days (the rebalance window)
        rolling_loss = realized_loss.rolling(20, min_periods=1).sum().fillna(0.0)
        # 5. Correct the factor values: subtract/penalize based on rolling realized loss (feedback gain = 2.0)
        corrected = values + 2.0 * rolling_loss
        return corrected
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
    _BASE_FACTOR_MEM_CACHE.clear()


def _panel_key(ast: dict, close, volume):
    body = {k: v for k, v in ast.items() if k != "thesis"}  # direction 参与=带符号
    h = _hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return (h, id(close), volume is not None)


def compute_dsl_factor(
    close: pd.DataFrame,
    volume: pd.DataFrame | None = None,
    *,
    ast: dict[str, Any],
    cache_mode: str = "disk",
) -> pd.DataFrame:
    """Compute a validated AutoResearch linear_combo AST(搜索内 memo 化)。"""
    if ast.get("type") != "linear_combo":
        raise ValueError("unsupported AutoResearch AST type: " + str(ast.get("type")))

    key = _panel_key(ast, close, volume)
    cached = _PANEL_CACHE.get(key)
    if cached is not None:
        return cached

    out = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for term in ast.get("terms", []):
        values = _call_factor(term["factor"], close, volume, term.get("params", {}), cache_mode=cache_mode)
        values = values.reindex(index=close.index, columns=close.columns)
        for op in term.get("transforms", []):
            values = _apply_transform(values, op, close=close)
        out = out.add(float(term.get("weight", 1.0)) * values, fill_value=0.0)

    if ast.get("direction") == "negative":
        out = -out
    out = out.replace([np.inf, -np.inf], np.nan)

    # Apply root-level AST transforms on the combined out panel
    for op in ast.get("transforms", []):
        out = _apply_transform(out, op, close=close)

    # 1. Apply Size & Industry Style Neutralization (事前特征中性化)
    neutralize_opts = ast.get("neutralize", [])
    if neutralize_opts:
        from lake.load_lake import load_daily_basic_panel, load_fundamental_panel
        neut_size = "size" in neutralize_opts
        neut_industry = "industry" in neutralize_opts

        log_size = None
        if neut_size:
            db_basic = load_daily_basic_panel(close.index, fields=["total_mv"])
            total_mv = db_basic.get("total_mv", pd.DataFrame())
            if total_mv.empty:
                # Fallback to rolling amount
                total_mv = close.mul(volume, fill_value=0.0).rolling(60).mean()
            log_size = np.log(total_mv.replace(0, np.nan))

        industry = None
        if neut_industry:
            db_fund = load_fundamental_panel(close.index, fields=["industry"])
            industry = db_fund.get("industry", pd.DataFrame())

        # Pre-align variables to close index/columns to compile numpy matrices
        log_size_aligned = log_size.reindex(index=close.index, columns=close.columns) if log_size is not None else None
        industry_aligned = industry.reindex(index=close.index, columns=close.columns).fillna("Unknown") if industry is not None else None

        # Prepare arrays
        out_arr = out.values.copy()
        log_size_arr = log_size_aligned.values if log_size_aligned is not None else None

        ind_dummies_arrs = []
        if industry_aligned is not None:
            unique_industries = sorted(list(set(np.unique(industry_aligned.values))))
            if "Unknown" in unique_industries:
                unique_industries.remove("Unknown")
            for ind_name in unique_industries:
                dummy_panel = (industry_aligned == ind_name).astype(float)
                ind_dummies_arrs.append(dummy_panel.values)

        # Fast cross-sectional regression in pure numpy
        for i in range(len(close.index)):
            y = out_arr[i]
            valid_mask = ~np.isnan(y)
            if log_size_arr is not None:
                valid_mask &= ~np.isnan(log_size_arr[i])

            n_valid = np.sum(valid_mask)
            if n_valid < 30:
                continue

            X_cols = [np.ones(n_valid)]
            if log_size_arr is not None:
                X_cols.append(log_size_arr[i, valid_mask])
            for dummy_arr in ind_dummies_arrs:
                X_cols.append(dummy_arr[i, valid_mask])

            X_clean = np.column_stack(X_cols)
            y_clean = y[valid_mask]

            try:
                coef, _, _, _ = np.linalg.lstsq(X_clean, y_clean, rcond=None)
                resids = y_clean - X_clean @ coef
                out_arr[i, valid_mask] = resids
            except Exception:
                continue

        # Re-construct DataFrame and Z-score to restore scaling
        out = pd.DataFrame(out_arr, index=close.index, columns=close.columns)
        out = out.replace([np.inf, -np.inf], np.nan)
        out = (out.sub(out.mean(axis=1), axis=0)).div(out.std(axis=1) + 1e-10, axis=0)

    _PANEL_CACHE[key] = out
    _PANEL_ORDER.append(key)
    if len(_PANEL_ORDER) > _PANEL_CACHE_MAX:
        _PANEL_CACHE.pop(_PANEL_ORDER.pop(0), None)
    return out
