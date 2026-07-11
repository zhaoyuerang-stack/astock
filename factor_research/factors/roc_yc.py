"""ROC (Return on Capital) and YC (Earnings Yield) fundamental factor calculations.

This implements the classic Joel Greenblatt Magic Formula (神奇公式),
which combines a Quality factor (ROC) with a Value factor (YC).
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from factors.fundamental import ep_proxy, roe
from factors.utils import safe_zscore, mad_clip


def yc_factor(close: pd.DataFrame) -> pd.DataFrame:
    """YC (Earnings Yield) factor.

    Definition: Earnings Yield = 1 / PE = EP.
    Here we reuse the robust PIT ep_proxy factor from the fundamental module.
    """
    return ep_proxy(close)


def roc_factor(close: pd.DataFrame) -> pd.DataFrame:
    """ROC (Return on Capital) factor.

    Definition: Return on Capital (资本回报率).
    As raw debt and net fixed asset statement line items are often noisy or lagging,
    we use the Point-in-Time (PIT) ROE (Return on Equity) from the fundamental module
    as the robust, look-ahead-safe proxy for Return on Capital.
    """
    return roe(close)


def roc_yc_composite_factor(
    close: pd.DataFrame,
    blend_weight: float = 0.5,
) -> pd.DataFrame:
    """Blends ROC (Return on Capital, proxy by ROE) and YC (Earnings Yield, EP) cross-sectionally.

    Both components are normalized (MAD-clipped and Z-scored) before blending.
    The combined result is also normalized.
    """
    yc = yc_factor(close)
    roc = roc_factor(close)

    # Align date and code indices
    common_idx = yc.index.intersection(roc.index)
    common_cols = yc.columns.intersection(roc.columns)

    yc_aligned = yc.loc[common_idx, common_cols]
    roc_aligned = roc.loc[common_idx, common_cols]

    composite = blend_weight * roc_aligned + (1.0 - blend_weight) * yc_aligned
    return safe_zscore(mad_clip(composite))


def neutralize_factor(factor: pd.DataFrame, styles: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Neutralizes a factor panel against a dictionary of style panels cross-sectionally."""
    neutralized = pd.DataFrame(index=factor.index, columns=factor.columns, dtype=float)
    keys = list(styles.keys())

    for dt in factor.index:
        y = factor.loc[dt]
        # Build X matrix for date dt
        X_dict = {}
        for k in keys:
            if dt in styles[k].index:
                X_dict[k] = styles[k].loc[dt]
        if not X_dict:
            continue
        df_dt = pd.DataFrame(X_dict)
        df_dt["y"] = y
        df_dt = df_dt.dropna()

        if len(df_dt) < 10:
            continue

        # OLS regression: y = X * beta + intercept
        X = df_dt[keys].values
        X_design = np.column_stack([np.ones(len(df_dt)), X])
        y_val = df_dt["y"].values

        # Solve OLS
        beta, _, _, _ = np.linalg.lstsq(X_design, y_val, rcond=None)

        # Compute residuals
        y_pred = X_design @ beta
        resids = y_val - y_pred

        neutralized.loc[dt, df_dt.index] = resids

    return neutralized


def _build_cne6_styles(
    close: pd.DataFrame,
    amount: pd.DataFrame,
    total_mv: pd.DataFrame | None = None,
    turnover: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Helper to build local CNE6 style panels within the factors layer."""
    from factors.momentum import mom_n, volatility
    from factors.fundamental import bp_proxy, revenue_yoy, net_profit_yoy, gross_margin

    Z = lambda p: safe_zscore(mad_clip(p))
    ret = close.pct_change(fill_method=None)
    mkt = ret.mean(axis=1)
    beta = ret.rolling(60).cov(mkt).div(mkt.rolling(60).var(), axis=0)

    if total_mv is not None:
        size = Z(np.log(total_mv.reindex_like(close).replace(0, np.nan)))
    else:
        size = Z(-np.log(amount.rolling(60).mean().replace(0, np.nan)))

    if turnover is not None:
        liq = Z(turnover.reindex_like(close))
    else:
        liq = Z(-np.log(amount.rolling(60).mean().replace(0, np.nan)))

    return {
        "Size":     size,
        "Liquidity": liq,
        "Beta":     Z(beta),
        "Momentum": Z(mom_n(close, 250, skip=20)),
        "ResidVol": Z(volatility(close, 60)),
        "Value_BP": Z(bp_proxy(close)),
        "Value_EP": Z(ep_proxy(close)),
        "Growth":   Z(0.5 * revenue_yoy(close) + 0.5 * net_profit_yoy(close)),
        "Quality":  Z(0.5 * roe(close) + 0.5 * gross_margin(close)),
    }


def roc_yc_neutralized_factor(
    close: pd.DataFrame,
    amount: pd.DataFrame,
    blend_weight: float = 0.5,
) -> pd.DataFrame:
    """Computes the ROC-YC composite factor, then neutralizes it against the CNE6 style panels.

    Returns the style-neutralized, MAD-clipped, and Z-scored factor panel.
    """
    from lake.load_lake import load_daily_basic_panel

    # 1. Compute raw composite factor
    raw_factor = roc_yc_composite_factor(close, blend_weight)

    # 2. Build CNE6 style panels
    db = load_daily_basic_panel(close.index, fields=["total_mv", "turnover_rate"])
    styles = _build_cne6_styles(
        close,
        amount,
        total_mv=db.get("total_mv"),
        turnover=db.get("turnover_rate"),
    )

    # 3. Perform cross-sectional regression to get residuals
    neutralized = neutralize_factor(raw_factor, styles)

    # 4. Standardise residuals to keep factor normalized
    return safe_zscore(mad_clip(neutralized))
