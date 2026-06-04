"""Candidate strategy definitions and grid generation for the stage-1 factory."""
from dataclasses import dataclass, asdict
from typing import Sequence

import numpy as np
import pandas as pd

from core.backtest import mad_clip, safe_zscore, small_cap_factor


@dataclass(frozen=True)
class Candidate:
    family: str
    version: str
    desc: str
    factors: Sequence[str]
    weights: Sequence[float]
    top_n: int = 25
    rebalance_days: int = 20
    leverage: float = 1.0
    timing: str = "small_cap_ma16"

    def to_dict(self):
        return asdict(self)


def _fund_panel(fundamentals, name, close):
    if not fundamentals or name not in fundamentals or fundamentals[name].empty:
        return pd.DataFrame(index=close.index, columns=close.columns, dtype=float)
    return fundamentals[name].reindex(index=close.index, columns=close.columns)


def _valuation_yield(value, price):
    price = price.reindex(index=value.index, columns=value.columns).replace(0, np.nan)
    return value.div(price).replace([np.inf, -np.inf], np.nan)


def _industry_rank(panel, industry):
    if industry is None or industry.empty:
        return pd.DataFrame(index=panel.index, columns=panel.columns, dtype=float)
    industry = industry.reindex(index=panel.index, columns=panel.columns)
    ranked = pd.DataFrame(index=panel.index, columns=panel.columns, dtype=float)
    for date in panel.index:
        values = panel.loc[date]
        groups = industry.loc[date]
        valid = values.notna() & groups.notna()
        if valid.any():
            ranked.loc[date, valid] = values[valid].groupby(groups[valid]).rank(pct=True)
    return ranked


def _industry_neutral(panel, industry):
    if industry is None or industry.empty:
        return pd.DataFrame(index=panel.index, columns=panel.columns, dtype=float)
    industry = industry.reindex(index=panel.index, columns=panel.columns)
    neutral = pd.DataFrame(index=panel.index, columns=panel.columns, dtype=float)
    for date in panel.index:
        values = panel.loc[date]
        groups = industry.loc[date]
        valid = values.notna() & groups.notna()
        if valid.any():
            medians = values[valid].groupby(groups[valid]).transform("median")
            neutral.loc[date, valid] = values[valid] - medians
    return neutral


def _ts_percentile(panel, window=756):
    return panel.rolling(window, min_periods=max(60, window // 4)).rank(pct=True)


def _fund_delta(panel, window=252):
    return panel - panel.shift(window)


def _capital_panel(capital, name, close):
    if not capital or name not in capital or capital[name].empty:
        return pd.DataFrame(index=close.index, columns=close.columns, dtype=float)
    return capital[name].reindex(index=close.index, columns=close.columns)


def factor_library(close, volume, amount, fundamentals=None, raw_close=None, capital=None):
    ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    market_ret = ret.mean(axis=1)
    market_var60 = market_ret.rolling(60).var() + 1e-8
    beta60 = ret.mul(market_ret, axis=0).rolling(60).mean().div(market_var60, axis=0)
    rel_amount20 = amount.rolling(20).mean() / (amount.rolling(120).mean() + 1e-6)
    vol20 = ret.rolling(20).std()
    trend60 = close / close.rolling(60).mean() - 1
    roe = _fund_panel(fundamentals, "roe", close)
    gross_margin = _fund_panel(fundamentals, "gross_margin", close)
    cfo_ps = _fund_panel(fundamentals, "cfo_ps", close)
    revenue_yoy = _fund_panel(fundamentals, "revenue_yoy", close)
    net_profit_yoy = _fund_panel(fundamentals, "net_profit_yoy", close)
    eps_ttm = _fund_panel(fundamentals, "eps_ttm", close)
    bps = _fund_panel(fundamentals, "bps", close)
    industry = _fund_panel(fundamentals, "industry", close)
    price_for_value = raw_close if raw_close is not None and not raw_close.empty else close
    eps_yield = _valuation_yield(eps_ttm, price_for_value)
    bp_value = _valuation_yield(bps, price_for_value)
    quality_value_regime = _industry_rank(roe, industry) * _ts_percentile(bp_value)
    growth_value_regime = _industry_rank(net_profit_yoy, industry) * _ts_percentile(bp_value)
    margin_balance = _capital_panel(capital, "margin_balance", close)
    margin_buy = _capital_panel(capital, "margin_buy", close)
    short_balance = _capital_panel(capital, "short_balance", close)
    north_hold_pct = _capital_panel(capital, "northbound_hold_pct", close)
    north_hold_value = _capital_panel(capital, "northbound_hold_value", close)
    north_value_chg_1d = _capital_panel(capital, "northbound_value_chg_1d", close)
    north_buy_value_1d = _capital_panel(capital, "northbound_buy_value_1d", close)
    margin_balance_chg5 = margin_balance.pct_change(5, fill_method=None)
    margin_balance_chg20 = margin_balance.pct_change(20, fill_method=None)
    margin_buy_ratio20 = margin_buy.rolling(20).sum() / (amount.rolling(20).sum() + 1e-6)
    short_balance_chg20 = short_balance.pct_change(20, fill_method=None)
    north_hold_chg5 = north_hold_pct - north_hold_pct.shift(5)
    north_hold_chg20 = north_hold_pct - north_hold_pct.shift(20)
    north_value_chg20 = north_hold_value.pct_change(20, fill_method=None)
    north_buy_ratio20 = north_buy_value_1d.rolling(20).sum() / (amount.rolling(20).sum() + 1e-6)
    return {
        "size20": small_cap_factor(amount, 20),
        "size40": small_cap_factor(amount, 40),
        "size60": small_cap_factor(amount, 60),
        "low_vol10": safe_zscore(mad_clip(-ret.rolling(10).std())),
        "low_vol20": safe_zscore(mad_clip(-ret.rolling(20).std())),
        "low_vol40": safe_zscore(mad_clip(-ret.rolling(40).std())),
        "reversal10": safe_zscore(mad_clip(-(close / close.shift(10) - 1))),
        "reversal20": safe_zscore(mad_clip(-(close / close.shift(20) - 1))),
        "reversal5": safe_zscore(mad_clip(-(close / close.shift(5) - 1))),
        "momentum_quality10": safe_zscore(mad_clip((ret > 0).rolling(10).mean())),
        "momentum_quality20": safe_zscore(mad_clip((ret > 0).rolling(20).mean())),
        "momentum_quality40": safe_zscore(mad_clip((ret > 0).rolling(40).mean())),
        "low_turnover5": safe_zscore(
            mad_clip(-(amount / (amount.rolling(60).mean() + 1e-6)).rolling(5).mean())
        ),
        "low_turnover10": safe_zscore(
            mad_clip(-(amount / (amount.rolling(60).mean() + 1e-6)).rolling(10).mean())
        ),
        "low_turnover20": safe_zscore(
            mad_clip(-(amount / (amount.rolling(60).mean() + 1e-6)).rolling(20).mean())
        ),
        "liquidity_dryup20": safe_zscore(mad_clip(-rel_amount20)),
        "liquidity_dryup60": safe_zscore(mad_clip(
            -(amount.rolling(60).mean() / (amount.rolling(180).mean() + 1e-6))
        )),
        "low_beta60": safe_zscore(mad_clip(-beta60)),
        "trend_stability60": safe_zscore(mad_clip(trend60 / (vol20 + 1e-6))),
        "trend_stability120": safe_zscore(mad_clip(
            (close / close.rolling(120).mean() - 1) / (ret.rolling(40).std() + 1e-6)
        )),
        "range_compression20": safe_zscore(mad_clip(-ret.rolling(20).std() / (ret.rolling(60).std() + 1e-6))),
        "price_below_ma20": safe_zscore(mad_clip(-(close / close.rolling(20).mean() - 1))),
        "price_below_ma60": safe_zscore(mad_clip(-(close / close.rolling(60).mean() - 1))),
        "fund_roe_quality": safe_zscore(mad_clip(roe)),
        "fund_gross_margin_quality": safe_zscore(mad_clip(gross_margin)),
        "fund_cfo_quality": safe_zscore(mad_clip(cfo_ps)),
        "fund_revenue_growth": safe_zscore(mad_clip(revenue_yoy)),
        "fund_profit_growth": safe_zscore(mad_clip(net_profit_yoy)),
        "fund_eps_yield": safe_zscore(mad_clip(eps_yield)),
        "fund_bp_value": safe_zscore(mad_clip(bp_value)),
        "fund_roe_ind_rank": safe_zscore(mad_clip(_industry_rank(roe, industry))),
        "fund_gross_margin_ind_rank": safe_zscore(mad_clip(_industry_rank(gross_margin, industry))),
        "fund_cfo_ind_rank": safe_zscore(mad_clip(_industry_rank(cfo_ps, industry))),
        "fund_revenue_growth_ind_rank": safe_zscore(mad_clip(_industry_rank(revenue_yoy, industry))),
        "fund_profit_growth_ind_rank": safe_zscore(mad_clip(_industry_rank(net_profit_yoy, industry))),
        "fund_eps_yield_ind_rank": safe_zscore(mad_clip(_industry_rank(eps_yield, industry))),
        "fund_bp_value_ind_rank": safe_zscore(mad_clip(_industry_rank(bp_value, industry))),
        "fund_roe_ind_neutral": safe_zscore(mad_clip(_industry_neutral(roe, industry))),
        "fund_profit_growth_ind_neutral": safe_zscore(mad_clip(_industry_neutral(net_profit_yoy, industry))),
        "fund_bp_value_ind_neutral": safe_zscore(mad_clip(_industry_neutral(bp_value, industry))),
        "fund_roe_delta": safe_zscore(mad_clip(_fund_delta(roe))),
        "fund_gross_margin_delta": safe_zscore(mad_clip(_fund_delta(gross_margin))),
        "fund_cfo_delta": safe_zscore(mad_clip(_fund_delta(cfo_ps))),
        "fund_profit_growth_delta": safe_zscore(mad_clip(_fund_delta(net_profit_yoy))),
        "fund_bp_value_pctile": safe_zscore(mad_clip(_ts_percentile(bp_value))),
        "fund_eps_yield_pctile": safe_zscore(mad_clip(_ts_percentile(eps_yield))),
        "fund_quality_value_regime": safe_zscore(mad_clip(quality_value_regime)),
        "fund_growth_value_regime": safe_zscore(mad_clip(growth_value_regime)),
        "margin_balance_chg5": safe_zscore(mad_clip(margin_balance_chg5)),
        "margin_balance_chg20": safe_zscore(mad_clip(margin_balance_chg20)),
        "margin_balance_drop20": safe_zscore(mad_clip(-margin_balance_chg20)),
        "margin_buy_ratio20": safe_zscore(mad_clip(margin_buy_ratio20)),
        "margin_buy_ratio_drop20": safe_zscore(mad_clip(-margin_buy_ratio20)),
        "short_balance_chg20": safe_zscore(mad_clip(short_balance_chg20)),
        "short_balance_drop20": safe_zscore(mad_clip(-short_balance_chg20)),
        "north_hold_chg5": safe_zscore(mad_clip(north_hold_chg5)),
        "north_hold_chg20": safe_zscore(mad_clip(north_hold_chg20)),
        "north_hold_drop20": safe_zscore(mad_clip(-north_hold_chg20)),
        "north_hold_pct_level": safe_zscore(mad_clip(north_hold_pct)),
        "north_hold_value_level": safe_zscore(mad_clip(np.log(north_hold_value + 1))),
        "north_buy_ratio20": safe_zscore(mad_clip(north_buy_ratio20)),
        "north_sell_ratio20": safe_zscore(mad_clip(-north_buy_ratio20)),
        "north_value_chg1": safe_zscore(mad_clip(north_value_chg_1d)),
        "north_value_chg20": safe_zscore(mad_clip(north_value_chg20)),
    }


def build_factor(candidate, library):
    total = sum(abs(w) for w in candidate.weights) or 1.0
    comp = 0
    for name, weight in zip(candidate.factors, candidate.weights):
        comp = comp + library[name] * (weight / total)
    return safe_zscore(comp)


def default_candidates():
    """Small first batch: enough to validate the factory, not a search yet."""
    return [
        Candidate("small-cap-size", "factory-baseline", "小盘60基线", ["size60"], [1.0], leverage=1.25),
        Candidate("low-vol", "v0.1", "低波20", ["low_vol20"], [1.0]),
        Candidate("reversal", "v0.1", "20日反转", ["reversal20"], [1.0]),
        Candidate("reversal", "v0.2", "5日反转", ["reversal5"], [1.0]),
        Candidate("momentum-quality", "v0.1", "上涨天数质量", ["momentum_quality20"], [1.0]),
        Candidate("liquidity-flow", "v0.1", "低换手/低关注", ["low_turnover10"], [1.0]),
        Candidate("mean-reversion-quality", "v0.1", "小盘+低波+反转", ["size60", "low_vol20", "reversal20"], [0.4, 0.3, 0.3]),
        Candidate("liquidity-quality", "v0.1", "低换手+低波+均线低位", ["low_turnover10", "low_vol20", "price_below_ma60"], [0.4, 0.3, 0.3]),
    ]


FACTOR_FAMILIES = {
    "size": ["size20", "size40", "size60"],
    "low-vol": ["low_vol10", "low_vol20", "low_vol40"],
    "reversal": ["reversal5", "reversal10", "reversal20"],
    "momentum-quality": ["momentum_quality10", "momentum_quality20", "momentum_quality40"],
    "liquidity-flow": ["low_turnover5", "low_turnover10", "low_turnover20"],
    "liquidity-quality": ["liquidity_dryup20", "liquidity_dryup60"],
    "beta-defensive": ["low_beta60", "range_compression20"],
    "trend-stability": ["trend_stability60", "trend_stability120"],
    "price-location": ["price_below_ma20", "price_below_ma60"],
    "fundamental-quality": ["fund_roe_quality", "fund_gross_margin_quality", "fund_cfo_quality"],
    "fundamental-growth": ["fund_revenue_growth", "fund_profit_growth"],
    "fundamental-value": ["fund_eps_yield", "fund_bp_value"],
    "fundamental-industry-rank": [
        "fund_roe_ind_rank", "fund_gross_margin_ind_rank", "fund_cfo_ind_rank",
        "fund_revenue_growth_ind_rank", "fund_profit_growth_ind_rank",
        "fund_eps_yield_ind_rank", "fund_bp_value_ind_rank",
    ],
    "fundamental-industry-neutral": [
        "fund_roe_ind_neutral", "fund_profit_growth_ind_neutral", "fund_bp_value_ind_neutral",
    ],
    "fundamental-change": [
        "fund_roe_delta", "fund_gross_margin_delta", "fund_cfo_delta", "fund_profit_growth_delta",
    ],
    "fundamental-value-pctile": ["fund_bp_value_pctile", "fund_eps_yield_pctile"],
    "fundamental-regime": ["fund_quality_value_regime", "fund_growth_value_regime"],
    "margin-flow": [
        "margin_balance_chg5", "margin_balance_chg20", "margin_balance_drop20",
        "margin_buy_ratio20", "margin_buy_ratio_drop20",
    ],
    "short-flow": ["short_balance_chg20", "short_balance_drop20"],
    "northbound-flow": [
        "north_hold_chg5", "north_hold_chg20", "north_hold_drop20",
        "north_hold_pct_level", "north_hold_value_level",
        "north_buy_ratio20", "north_sell_ratio20",
        "north_value_chg1", "north_value_chg20",
    ],
}


def _candidate_family(factors):
    tags = []
    for family, names in FACTOR_FAMILIES.items():
        if any(f in names for f in factors):
            tags.append(family)
    if tags == ["size"]:
        return "small-cap-size"
    if len(tags) == 1:
        return tags[0]
    return "-".join(tags[:3])


def _version(prefix, i):
    return f"{prefix}.{i:03d}"


def grid_candidates(limit=None):
    """Deterministic first grid for stage 1.2.

    It expands across factor choices, simple two/three-factor blends, holding
    breadth and rebalance frequency. This is still enumeration, not NSGA-II.
    """
    candidates = []
    top_ns = [20, 25, 40, 80]
    rebalances = [10, 20, 40, 60]

    base_factors = [name for names in FACTOR_FAMILIES.values() for name in names]
    i = 1
    for top_n in top_ns:
        for rebal in rebalances:
            for factor in base_factors:
                candidates.append(Candidate(
                    _candidate_family([factor]), _version("grid", i),
                    f"{factor} top{top_n} reb{rebal}",
                    [factor], [1.0], top_n=top_n, rebalance_days=rebal,
                    leverage=1.0 if factor != "size60" else 1.25,
                ))
                i += 1

    blend_specs = [
        (("size60", "low_vol20"), (0.5, 0.5)),
        (("size60", "reversal20"), (0.5, 0.5)),
        (("size60", "low_turnover10"), (0.5, 0.5)),
        (("low_vol20", "reversal20"), (0.5, 0.5)),
        (("low_turnover10", "low_vol20"), (0.5, 0.5)),
        (("low_turnover10", "price_below_ma60"), (0.5, 0.5)),
        (("liquidity_dryup20", "low_beta60"), (0.5, 0.5)),
        (("trend_stability60", "range_compression20"), (0.5, 0.5)),
        (("liquidity_dryup60", "price_below_ma60"), (0.5, 0.5)),
        (("size60", "low_vol20", "reversal20"), (0.4, 0.3, 0.3)),
        (("low_turnover10", "low_vol20", "price_below_ma60"), (0.4, 0.3, 0.3)),
        (("liquidity_dryup20", "low_beta60", "price_below_ma60"), (0.4, 0.3, 0.3)),
        (("trend_stability60", "momentum_quality20", "range_compression20"), (0.4, 0.3, 0.3)),
        (("fund_roe_quality", "fund_cfo_quality"), (0.5, 0.5)),
        (("fund_revenue_growth", "fund_profit_growth"), (0.5, 0.5)),
        (("fund_eps_yield", "fund_bp_value"), (0.5, 0.5)),
        (("fund_roe_quality", "fund_eps_yield", "fund_cfo_quality"), (0.4, 0.3, 0.3)),
        (("fund_roe_ind_rank", "fund_bp_value_ind_rank"), (0.5, 0.5)),
        (("fund_profit_growth_ind_rank", "fund_bp_value_pctile"), (0.5, 0.5)),
        (("fund_roe_delta", "fund_gross_margin_delta"), (0.5, 0.5)),
        (("fund_quality_value_regime", "fund_profit_growth_ind_rank"), (0.6, 0.4)),
        (("fund_growth_value_regime", "fund_bp_value_ind_neutral"), (0.6, 0.4)),
        (("margin_balance_chg20", "margin_buy_ratio20"), (0.5, 0.5)),
        (("margin_balance_drop20", "low_beta60"), (0.5, 0.5)),
        (("north_hold_chg20", "north_value_chg20"), (0.5, 0.5)),
        (("margin_balance_chg20", "north_hold_chg20"), (0.5, 0.5)),
        (("north_hold_pct_level", "north_buy_ratio20"), (0.5, 0.5)),
        (("north_hold_value_level", "north_hold_chg20"), (0.5, 0.5)),
    ]
    for factors, weights in blend_specs:
        for top_n in top_ns:
            for rebal in rebalances:
                candidates.append(Candidate(
                    _candidate_family(factors), _version("blend", i),
                    f"{'+'.join(factors)} top{top_n} reb{rebal}",
                    list(factors), list(weights), top_n=top_n,
                    rebalance_days=rebal, leverage=1.0,
                ))
                i += 1

    return candidates[:limit] if limit else candidates
