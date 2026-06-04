"""Unified data_lake backtest core with realistic costs."""
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from lake.load_lake import load_prices, load_raw_close


TARGET_ANNUAL = 0.35
TARGET_MAXDD = 0.15


@dataclass(frozen=True)
class CostModel:
    """Execution cost assumptions.

    Buy/sell costs are charged on traded notional. Financing cost is charged
    on borrowed exposure, i.e. max(leverage - 1, 0), on invested days.
    """

    buy_cost: float = 0.00225
    sell_cost: float = 0.00275
    financing_rate: float = 0.065


@dataclass(frozen=True)
class StrategyConfig:
    family: str = "small-cap-size"
    version: str = "v2.0"
    start: str = "2018-01-01"
    size_window: int = 60
    timing_ma: int = 16
    top_n: int = 25
    rebalance_days: int = 20
    leverage: float = 1.25
    cost: CostModel = CostModel()

    def to_dict(self):
        data = asdict(self)
        return data


def safe_zscore(df):
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1) + 1e-8, axis=0)


def mad_clip(df, n=5):
    med = df.median(axis=1)
    mad = df.sub(med, axis=0).abs().median(axis=1)
    return df.clip(lower=med - n * mad, upper=med + n * mad, axis=0)


def load_price_panels(start="2010-01-01"):
    px = load_prices(start=start, fields=("close", "volume"))
    raw = load_raw_close(start=start)
    # 成交额按【不复权价】重算(原 amount=volume×复权close,复权因子逐股不同,会污染
    # small_cap_factor/timing 的截面排序);volume 单位是手,×100 还原成股得真实成交额(元)。
    amount = px["volume"] * 100 * raw.reindex(index=px["volume"].index, columns=px["volume"].columns)
    return px["close"], px["volume"], amount


def small_cap_factor(amount, window=60):
    return safe_zscore(mad_clip(-np.log(amount.rolling(window).mean() + 1)))


def small_cap_timing(close, amount, ma_window=16):
    ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
    small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
    small_nav = (1 + small_idx.fillna(0)).cumprod()
    timing = (small_nav > small_nav.rolling(ma_window).mean()).shift(1, fill_value=False).astype(bool)
    dist = small_nav / small_nav.rolling(ma_window).mean() - 1
    return timing, small_nav, dist


def build_rebalance_weights(factor, close, top_n, rebalance_days):
    fdates = factor.dropna(how="all").index.intersection(close.index)
    if len(fdates) < 100:
        return {}

    weights = {}
    for rd in list(fdates[::rebalance_days]):
        pos = close.index.get_loc(rd)
        if pos + 1 >= len(close.index):
            continue
        effective = close.index[pos + 1]
        f = factor.loc[rd].dropna()
        active = close.loc[rd].dropna().index
        f = f.reindex(active).dropna()
        if len(f) < top_n:
            continue
        weights[effective] = pd.Series(1.0 / top_n, index=f.nlargest(top_n).index)
    return weights


def backtest_weights(close, scheduled_weights, timing_signal=None, config=StrategyConfig()):
    """Daily vector backtest with turnover, timing exits, leverage and financing."""
    daily_ret = (
        close.pct_change(fill_method=None)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    dates = list(close.index)
    cols = list(close.columns)
    col_idx = {c: i for i, c in enumerate(cols)}

    current_selected = pd.Series(dtype=float)
    current_weight = np.zeros(len(cols))
    out = np.full(len(dates), np.nan)
    turnover = np.zeros(len(dates))
    cost_paid = np.zeros(len(dates))

    for i, dt in enumerate(dates):
        if i == 0:
            continue
        if dt in scheduled_weights:
            current_selected = scheduled_weights[dt]

        # Timing signal is a daily exposure multiplier in [0, 1]. Binary masks
        # (True/False) collapse to 1.0/0.0, so legacy small-cap timing is
        # unchanged; vol-target genes pass a fractional exposure to de-risk.
        exposure = 1.0
        if timing_signal is not None:
            exposure = float(timing_signal.reindex([dt]).fillna(0.0).iloc[0])
            exposure = min(max(exposure, 0.0), 1.0)

        target_weight = np.zeros(len(cols))
        if exposure > 0 and len(current_selected):
            for code, weight in current_selected.items():
                j = col_idx.get(code)
                if j is not None:
                    target_weight[j] = weight * exposure

        delta = target_weight - current_weight
        buy_turnover = float(delta[delta > 0].sum())
        sell_turnover = float((-delta[delta < 0]).sum())
        trade_cost = (
            buy_turnover * config.cost.buy_cost
            + sell_turnover * config.cost.sell_cost
        ) * config.leverage

        day_ret = np.asarray(daily_ret.iloc[i].values, dtype="float64")
        day_ret[~np.isfinite(day_ret)] = 0.0
        # Bad source ticks can create impossible finite returns; keep evaluation stable.
        day_ret = np.clip(day_ret, -1.0, 10.0)
        held = target_weight != 0
        gross_ret = float((day_ret[held] * target_weight[held]).sum()) * config.leverage
        financing = 0.0
        if target_weight.sum() > 0 and config.leverage > 1:
            financing = (config.leverage - 1.0) * config.cost.financing_rate / 252.0

        out[i] = gross_ret - trade_cost - financing
        turnover[i] = buy_turnover + sell_turnover
        cost_paid[i] = trade_cost + financing
        current_weight = target_weight

    ret = pd.Series(out, index=dates).dropna()
    detail = pd.DataFrame(
        {"ret": ret, "turnover": turnover[1:], "cost": cost_paid[1:]},
        index=ret.index,
    )
    return ret, detail


def run_small_cap_strategy(config=StrategyConfig()):
    close, volume, amount = load_price_panels(config.start)
    factor = small_cap_factor(amount, config.size_window)
    timing, small_nav, timing_dist = small_cap_timing(close, amount, config.timing_ma)
    scheduled = build_rebalance_weights(factor, close, config.top_n, config.rebalance_days)
    ret, detail = backtest_weights(close, scheduled, timing, config)
    return {
        "close": close,
        "volume": volume,
        "amount": amount,
        "factor": factor,
        "timing": timing,
        "timing_dist": timing_dist,
        "scheduled_weights": scheduled,
        "returns": ret,
        "detail": detail,
    }


def latest_signal(config=StrategyConfig()):
    result = run_small_cap_strategy(config)
    close = result["close"]
    factor = result["factor"]
    timing = result["timing"]
    dist = result["timing_dist"]
    last = close.index[-1]
    f = factor.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(config.top_n).index.tolist()
    return {
        "date": last,
        "in_market": bool(timing.loc[last]),
        "timing_dist": float(dist.loc[last]),
        "holdings": holdings,
        "result": result,
    }


def metrics(ret):
    if len(ret) < 100:
        return {
            "annual": -1,
            "vol": 0,
            "sharpe": -1,
            "maxdd": -1,
            "calmar": 0,
            "hit": False,
            "n": len(ret),
        }
    annual = ret.mean() * 252
    vol = ret.std() * np.sqrt(252)
    sharpe = annual / vol if vol > 0 else 0
    cum = (1 + ret).cumprod()
    maxdd = (cum / cum.cummax() - 1).min()
    calmar = annual / abs(maxdd) if maxdd < 0 else 0
    hit = (annual >= TARGET_ANNUAL) and (abs(maxdd) <= TARGET_MAXDD)
    return {
        "annual": annual,
        "vol": vol,
        "sharpe": sharpe,
        "maxdd": maxdd,
        "calmar": calmar,
        "hit": hit,
        "n": len(ret),
    }


def yearly_returns(ret):
    return ret.groupby(ret.index.year).apply(lambda x: (1 + x).prod() - 1)
