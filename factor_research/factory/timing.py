"""Regime timing genes that are independent of the small-cap relative strength.

Background (LESSONS): every factory candidate previously shared
``small_cap_ma16``. That timing exits whenever the *small-cap* equal-weight
index loses its MA, so any candidate inherits the small-cap baseline's bull/bear
calendar and its return correlation gets pulled up to 0.72+. The structural
conflict "low correlation vs drawdown control" lives entirely in the timing
layer, not the factors.

This module adds timing genes driven by **market-wide** regime variables
(whole-market trend / realized volatility / breadth, large-cap 沪深300 proxy
trend) and **never** by small-cap relative strength. They give fundamental /
defensive sleeves a way to control drawdown without re-synchronising with the
small-cap baseline.

Look-ahead discipline: every regime series is built from returns/prices up to
and including T, then ``.shift(1)`` so the position on day T only uses
information available at T-1. Vol-target genes return a *continuous* exposure
multiplier in [0, 1]; binary genes return a boolean-as-float in-market mask.
Both are consumed by ``core.backtest.backtest_weights`` (which reindex/fillna
the signal per day).
"""
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Market-wide regime building blocks (all use only past data after shift)
# ---------------------------------------------------------------------------
def _market_return(close):
    """Equal-weight return across all active names (whole-market proxy)."""
    ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    return ret.mean(axis=1)


def _bigcap_nav(close, amount, n=300):
    """Large-cap (沪深300-like) equal-weight NAV from the top-amount names.

    Membership is decided each day by trailing 60-day average amount, so it
    drifts with liquidity but never peeks at future prices.
    """
    ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    amt60 = amount.rolling(60).mean()
    big_mask = amt60.rank(axis=1, ascending=False) <= n
    big_ret = (ret * big_mask).sum(axis=1) / big_mask.sum(axis=1).replace(0, np.nan)
    return (1 + big_ret.fillna(0)).cumprod()


def _market_vol(close, window=20):
    """Annualised realised vol of the equal-weight market return."""
    return _market_return(close).rolling(window).std() * np.sqrt(252)


def _market_breadth(close, ma_window=20):
    """Fraction of names trading above their own moving average."""
    above = close > close.rolling(ma_window).mean()
    return above.sum(axis=1) / close.notna().sum(axis=1).replace(0, np.nan)


# ---------------------------------------------------------------------------
# Timing genes
# ---------------------------------------------------------------------------
def always_in(close):
    """No timing: always fully invested (drawdown control comes from factors)."""
    return pd.Series(1.0, index=close.index)


def bigcap_trend(close, amount, ma_window=200):
    """Binary: in-market when the large-cap proxy is above its MA(ma_window).

    Regime variable = 沪深300-like trend. Independent of small-cap strength.
    """
    nav = _bigcap_nav(close, amount)
    in_mkt = (nav > nav.rolling(ma_window).mean())
    return in_mkt.shift(1, fill_value=False).astype(float)


def market_trend(close, ma_window=120):
    """Binary: in-market when the whole-market NAV is above its MA(ma_window)."""
    nav = (1 + _market_return(close).fillna(0)).cumprod()
    in_mkt = (nav > nav.rolling(ma_window).mean())
    return in_mkt.shift(1, fill_value=False).astype(float)


def vol_target(close, target_vol=0.18, window=20, cap=1.0, floor=0.0):
    """Continuous exposure = target_vol / realised_market_vol, clipped to [floor, cap].

    High whole-market vol -> scale down; low vol -> scale up to the cap. This is
    a risk-control gene, orthogonal to which stocks are cheap/expensive.
    """
    vol = _market_vol(close, window=window)
    exposure = (target_vol / vol).clip(lower=floor, upper=cap)
    return exposure.shift(1).fillna(0.0)


def vol_target_trend(close, amount, target_vol=0.18, window=20, ma_window=200, cap=1.0):
    """Vol-target exposure gated to 0 when the large-cap proxy is below its MA.

    Combines a risk-off bear filter (large-cap trend, NOT small-cap) with
    continuous vol scaling in the bull regime.
    """
    exposure = vol_target(close, target_vol=target_vol, window=window, cap=cap)
    trend = bigcap_trend(close, amount, ma_window=ma_window)
    return (exposure * trend).clip(lower=0.0, upper=cap)


def breadth_vol_target(close, target_vol=0.18, window=20, breadth_floor=0.30, cap=1.0):
    """Vol-target exposure gated to 0 when market breadth collapses.

    Breadth (fraction above own MA20) is a whole-market participation gauge;
    when it drops below ``breadth_floor`` the regime is treated as risk-off.
    """
    exposure = vol_target(close, target_vol=target_vol, window=window, cap=cap)
    breadth = _market_breadth(close).shift(1)
    gate = (breadth >= breadth_floor).astype(float)
    return (exposure * gate).clip(lower=0.0, upper=cap)


def mkt_drawdown_stop(close, stop=-0.08, reentry=0.0):
    """Binary: go flat when the equal-weight market NAV draws down past ``stop``.

    Regime variable = whole-market drawdown state (NAV vs its trailing peak).
    This is a circuit breaker that directly targets the binding constraint
    (pressure drawdown) rather than a slow trend MA. It is *market-wide*, not
    small-cap relative strength: every name contributes equally to the index.

    re-entry: stay flat until the market has recovered to within ``reentry`` of
    a fresh peak (default 0 = re-enter as soon as drawdown is shallower than
    ``stop``). Decision on day T uses NAV through T-1 (shift(1)).
    """
    nav = (1 + _market_return(close).fillna(0)).cumprod()
    dd = nav / nav.cummax() - 1
    if reentry <= 0:
        in_mkt = dd > stop
    else:
        # Hysteresis: exit at stop, re-enter only above (stop + reentry).
        state = []
        on = True
        for d in dd:
            if on and d <= stop:
                on = False
            elif (not on) and d >= (stop + reentry):
                on = True
            state.append(on)
        in_mkt = pd.Series(state, index=dd.index)
    return in_mkt.shift(1, fill_value=True).astype(float)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
# Spec string -> daily exposure/mask Series the backtester multiplies into
# target weights. Keeping the small-cap gene reachable here too means the
# dispatcher is the single source of truth, but it delegates back to core to
# avoid duplicating that logic.
def build_timing(spec, close, amount):
    """Resolve a timing spec string into a daily exposure/mask Series.

    Unknown specs fall back to ``small_cap_ma16`` so legacy candidates keep
    their original behaviour.
    """
    spec = spec or "small_cap_ma16"

    if spec == "none":
        return always_in(close)
    if spec.startswith("small_cap_ma"):
        from core.backtest import small_cap_timing

        ma = int(spec.replace("small_cap_ma", "")) if spec != "small_cap_ma16" else 16
        timing, _, _ = small_cap_timing(close, amount, ma)
        return timing.astype(float)
    if spec.startswith("bigcap_trend"):
        ma = int(spec.split("_")[-1]) if spec[-1].isdigit() else 200
        return bigcap_trend(close, amount, ma_window=ma)
    if spec.startswith("market_trend"):
        ma = int(spec.split("_")[-1]) if spec[-1].isdigit() else 120
        return market_trend(close, ma_window=ma)
    if spec.startswith("vol_target_trend"):
        # vol_target_trend_<tv*100>_<ma>, e.g. vol_target_trend_18_200
        parts = spec.split("_")
        tv = int(parts[3]) / 100.0 if len(parts) > 3 else 0.18
        ma = int(parts[4]) if len(parts) > 4 else 200
        return vol_target_trend(close, amount, target_vol=tv, ma_window=ma)
    if spec.startswith("breadth_vol_target"):
        # breadth_vol_target_<tv*100>_<floor*100>
        parts = spec.split("_")
        tv = int(parts[3]) / 100.0 if len(parts) > 3 else 0.18
        floor = int(parts[4]) / 100.0 if len(parts) > 4 else 0.30
        return breadth_vol_target(close, target_vol=tv, breadth_floor=floor)
    if spec.startswith("mkt_dd_stop_voltgt"):
        # mkt_dd_stop_voltgt_<stop*100>_<reentry*100>_<tv*100>
        parts = spec.split("_")
        stop = -int(parts[4]) / 100.0 if len(parts) > 4 else -0.08
        reentry = int(parts[5]) / 100.0 if len(parts) > 5 else 0.0
        tv = int(parts[6]) / 100.0 if len(parts) > 6 else 0.16
        gate = mkt_drawdown_stop(close, stop=stop, reentry=reentry)
        return (gate * vol_target(close, target_vol=tv)).clip(0.0, 1.0)
    if spec.startswith("mkt_dd_stop"):
        # mkt_dd_stop_<stop*100>_<reentry*100>, e.g. mkt_dd_stop_8_3
        parts = spec.split("_")
        stop = -int(parts[3]) / 100.0 if len(parts) > 3 else -0.08
        reentry = int(parts[4]) / 100.0 if len(parts) > 4 else 0.0
        return mkt_drawdown_stop(close, stop=stop, reentry=reentry)
    if spec.startswith("vol_target"):
        # vol_target_<tv*100>, e.g. vol_target_18
        parts = spec.split("_")
        tv = int(parts[2]) / 100.0 if len(parts) > 2 else 0.18
        return vol_target(close, target_vol=tv)

    # Unknown -> legacy fallback.
    from core.backtest import small_cap_timing

    timing, _, _ = small_cap_timing(close, amount, 16)
    return timing.astype(float)


# Independent (non small-cap) timing genes the factory may explore. Used by
# search space / island configs so the small-cap gene is not the only option.
INDEPENDENT_TIMING_GENES = [
    "none",
    "bigcap_trend_200",
    "bigcap_trend_120",
    "market_trend_120",
    "vol_target_15",
    "vol_target_18",
    "vol_target_trend_18_200",
    "vol_target_trend_15_200",
    "breadth_vol_target_18_30",
    # Market drawdown circuit breaker: the strongest independent lever found in
    # the timing experiment (directly targets pressure drawdown, corr ~0.4).
    "mkt_dd_stop_5_0",
    "mkt_dd_stop_8_3",
    "mkt_dd_stop_10_4",
    "mkt_dd_stop_voltgt_8_3_16",
]
