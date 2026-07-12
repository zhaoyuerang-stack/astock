"""ADV-linked square-root market impact (research / Gate-6 capacity layer).

This module does **not** lower the formal ``CostModel`` floor. Formal backtests
still pay canonical buy/sell rates; ADV impact is an **additive research overlay**
used for capacity curves and stress screens.

Model (buy-side square-root law, same as Gate 6):

    participation = trade_cny / ADV
    single_day_slippage = Y * vol * sqrt(participation)
    multi-day: min_N [ single_day / sqrt(N) + (N-1) * alpha_decay ]

See ``docs/cost_model.md`` §5.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

DEFAULT_ADV_WINDOW = 20
DEFAULT_VOL_WINDOW = 20
DEFAULT_VOL_FILL = 0.02
DEFAULT_Y = 1.0
DEFAULT_ALPHA_DECAY = 0.001  # 10 bps / day delayed execution
DEFAULT_MAX_SPLIT_DAYS = 5
DEFAULT_AUM_SCALES: tuple[float, ...] = (
    5_000_000,
    50_000_000,
    500_000_000,
    2_000_000_000,
)


def rolling_adv_cny(
    amount: pd.DataFrame,
    *,
    window: int = DEFAULT_ADV_WINDOW,
) -> pd.DataFrame:
    """20d rolling average daily turnover in CNY (from price panel ``amount``)."""
    return amount.rolling(window, min_periods=max(1, window // 2)).mean()


def rolling_daily_vol(
    close: pd.DataFrame,
    *,
    window: int = DEFAULT_VOL_WINDOW,
    fill: float = DEFAULT_VOL_FILL,
) -> pd.DataFrame:
    daily_ret = close.pct_change(fill_method=None)
    return daily_ret.rolling(window, min_periods=max(1, window // 2)).std().fillna(fill)


def weight_turnover(weights: pd.DataFrame) -> pd.DataFrame:
    """Absolute day-over-day weight change (fraction of NAV per name)."""
    return weights.diff().abs().fillna(0.0)


def participation_rate(
    trade_cny: pd.DataFrame,
    adv_cny: pd.DataFrame,
    *,
    cap: float = 0.5,
) -> pd.DataFrame:
    adv_aligned = adv_cny.reindex_like(trade_cny)
    part = trade_cny / (adv_aligned + 1.0)
    return part.clip(lower=0.0, upper=cap)


def square_root_slippage(
    participation: pd.DataFrame,
    vol: pd.DataFrame,
    *,
    y: float = DEFAULT_Y,
) -> pd.DataFrame:
    """Impact = Y * vol * sqrt(participation) (fraction of price, not bps)."""
    vol_a = vol.reindex_like(participation).fillna(DEFAULT_VOL_FILL)
    return y * vol_a * np.sqrt(participation.clip(lower=0.0))


def multi_day_optimized_impact(
    single_day_slippage: pd.DataFrame,
    *,
    max_days: int = DEFAULT_MAX_SPLIT_DAYS,
    alpha_decay: float = DEFAULT_ALPHA_DECAY,
) -> pd.DataFrame:
    """Min over N=1..max_days of single/sqrt(N) + (N-1)*alpha_decay."""
    costs = []
    for n in range(1, max_days + 1):
        costs.append(single_day_slippage / np.sqrt(n) + (n - 1) * alpha_decay)
    stacked = np.stack([c.to_numpy(dtype=float) for c in costs], axis=0)
    min_cost = np.min(stacked, axis=0)
    return pd.DataFrame(
        min_cost,
        index=single_day_slippage.index,
        columns=single_day_slippage.columns,
    )


def portfolio_daily_impact(
    impact_by_name: pd.DataFrame,
    weights: pd.DataFrame,
) -> pd.Series:
    """Portfolio-level daily impact ≈ sum_i impact_i * |w_i| (weight-weighted)."""
    w = weights.reindex_like(impact_by_name).fillna(0.0)
    return (impact_by_name * w.abs()).sum(axis=1)


def adv_impact_for_aum(
    *,
    amount: pd.DataFrame,
    close: pd.DataFrame,
    weights: pd.DataFrame,
    aum: float,
    y: float = DEFAULT_Y,
    alpha_decay: float = DEFAULT_ALPHA_DECAY,
    max_split_days: int = DEFAULT_MAX_SPLIT_DAYS,
) -> pd.Series:
    """Research-layer daily ADV impact series at a given AUM (CNY).

    Does not replace formal CostModel turnover costs — subtract from net
    returns only in capacity / stress screens.
    """
    adv = rolling_adv_cny(amount)
    vol = rolling_daily_vol(close)
    w_diff = weight_turnover(weights)
    trade_cny = w_diff * float(aum)
    part = participation_rate(trade_cny, adv)
    single = square_root_slippage(part, vol, y=y)
    impact = multi_day_optimized_impact(
        single, max_days=max_split_days, alpha_decay=alpha_decay
    )
    return portfolio_daily_impact(impact, weights)


def capacity_curve(
    *,
    base_returns: pd.Series,
    amount: pd.DataFrame,
    close: pd.DataFrame,
    weights: pd.DataFrame,
    aum_scales: Sequence[float] = DEFAULT_AUM_SCALES,
    y: float = DEFAULT_Y,
    alpha_decay: float = DEFAULT_ALPHA_DECAY,
    max_split_days: int = DEFAULT_MAX_SPLIT_DAYS,
) -> dict[str, dict[str, float]]:
    """Net performance after ADV impact overlay at each AUM scale.

    ``base_returns`` should already include formal CostModel turnover costs
    (Gate 6 1x path). ADV impact is added on top — never used to justify
    lowering the formal floor.
    """
    out: dict[str, dict[str, float]] = {}
    for scale in aum_scales:
        daily_impact = adv_impact_for_aum(
            amount=amount,
            close=close,
            weights=weights,
            aum=float(scale),
            y=y,
            alpha_decay=alpha_decay,
            max_split_days=max_split_days,
        )
        net = base_returns - daily_impact.reindex(base_returns.index).fillna(0.0)
        ann = float(net.mean() * 252)
        vol = float(net.std() * np.sqrt(252))
        sr = float(ann / vol) if vol > 0 else 0.0
        wealth = (1.0 + net).cumprod()
        dd = float((wealth / wealth.cummax() - 1.0).min()) if len(wealth) else 0.0
        out[str(int(scale)) if float(scale).is_integer() else str(scale)] = {
            "annual": ann,
            "sharpe": sr,
            "maxdd": dd,
            "aum": float(scale),
        }
    return out


def summarize_capacity_limit(
    curve: Mapping[str, Mapping[str, float]],
    *,
    min_sharpe: float = 0.5,
    min_annual: float = 0.05,
) -> tuple[float | None, list[str]]:
    """First AUM where net Sharpe/annual breach thresholds; reasons list."""
    reasons: list[str] = []
    ordered = sorted(curve.items(), key=lambda kv: float(kv[1].get("aum", kv[0])))
    for _key, perf in ordered:
        aum = float(perf.get("aum", 0.0))
        if perf.get("sharpe", 0.0) < min_sharpe or perf.get("annual", 0.0) < min_annual:
            reasons.append(
                f"Capacity limit reached at {aum / 1e6:.1f}M: "
                f"Net Sharpe={perf.get('sharpe', 0):.2f}, Return={perf.get('annual', 0):.1%}"
            )
            return aum, reasons
    if ordered:
        return float(ordered[-1][1].get("aum", 0.0)), reasons
    return None, reasons
