"""TOC Chip/AI Compute Bottleneck Strategy.

Filters the universe to ChiNext and STAR tech boards, uses the second derivative
of gross profit margin YoY (acceleration) as the alpha signal, restricts to ROE > 6%,
and runs under the unified BacktestEngine.
"""
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from factors.utils import safe_zscore, mad_clip
from lake.load_lake import load_prices, load_raw_close, load_fina_indicator_panel
from research_toolkit import apply_veto_filter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyConfig:
    family: str = "ai-compute-toc"
    version: str = "v1.0"
    start: str = "2018-01-01"
    rebalance_days: int = 20
    top_n: int = 10
    roe_threshold: float = 6.0
    accel_diff: int = 63
    leverage: float = 1.0
    cost: CostModel = CostModel()

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_price_panels(start="2010-01-01"):
    """Load tech-board close/volume/amount panels."""
    from lake.units import implied_amount

    px = load_prices(start=start, fields=("close", "volume"))
    raw = load_raw_close(start=start)
    amount = implied_amount(px["volume"], raw)
    close, volume = px["close"], px["volume"]
    
    # Filter to tech boards (ChiNext 30 and STAR 688)
    tech_cols = [c for c in close.columns if str(c).startswith("30") or str(c).startswith("688")]
    close = close[tech_cols]
    volume = volume[tech_cols]
    amount = amount[tech_cols]
    
    # Truncate tail where raw prices lag
    valid = amount.notna().sum(axis=1)
    if len(valid) > 5:
        typical = valid.iloc[-60:].median()
        good = valid[valid >= typical * 0.7]
        if len(good):
            cutoff = good.index[-1]
            close, volume, amount = close.loc[:cutoff], volume.loc[:cutoff], amount.loc[:cutoff]
            
    return close, volume, amount


# ---------------------------------------------------------------------------
# Factor and Timing builder
# ---------------------------------------------------------------------------

def build_factor(close, trade_dates, accel_diff=63):
    """Build TOC gross margin acceleration factor (date x code) without masking."""
    codes = list(close.columns)
    # load_fina_indicator_panel has ann_date PIT alignment
    fina = load_fina_indicator_panel(trade_dates, codes=codes, fields=["grossprofit_margin"])
    margin_panel = fina["grossprofit_margin"].shift(1)

    # Factor calculation
    margin_yoy = margin_panel.diff(250)
    margin_accel = margin_yoy.diff(accel_diff).replace(0.0, np.nan).ffill()

    return safe_zscore(mad_clip(margin_accel))


def build_timing(close, amount, ma_window=16):
    """Trend-following timing signal on equal-weighted tech index."""
    # Tech equal-weighted index return
    daily_ret = close.pct_change(fill_method=None).fillna(0.0)
    tech_idx_ret = daily_ret.mean(axis=1).fillna(0.0)
    tech_nav = (1 + tech_idx_ret).cumprod()
    
    tech_ma = tech_nav.rolling(ma_window).mean()
    # T-1 index state decides T-day position
    timing = (tech_nav > tech_ma).shift(1, fill_value=False).astype(bool)
    dist = tech_nav / tech_ma - 1
    return timing, tech_nav, dist


def build_rebalance_weights(factor, close, amount, roe_panel, top_n, rebalance_days, roe_thresh=6.0):
    """Convert factor to target weights at rebalancing dates with liquidity and ROE filters."""
    fdates = factor.dropna(how="all").index.intersection(close.index)
    fdates = fdates[fdates >= "2010-06-01"]
    if len(fdates) < 20:
        return {}

    # Liquidity rank inside tech board universe
    liq_rank = amount.rolling(20).mean().rank(axis=1, ascending=False)
    universe_mask = (liq_rank <= 500) & close.notna()
    roe_mask = roe_panel > roe_thresh

    weights = {}
    for rd in list(fdates[::rebalance_days]):
        pos = close.index.get_loc(rd)
        if pos + 1 >= len(close.index):
            continue
        effective = close.index[pos + 1]
        
        # Apply masks at rebalance date
        mask_rd = universe_mask.loc[rd] & roe_mask.loc[rd]
        f = factor.loc[rd].where(mask_rd).dropna()
        active = close.loc[rd].dropna().index
        f = f.reindex(active).dropna()
        
        if len(f) >= top_n:
            selected = pd.Series(1.0 / top_n, index=f.nlargest(top_n).index, dtype="float64")
            weights[effective] = selected
    return weights


# ---------------------------------------------------------------------------
# Run Strategy
# ---------------------------------------------------------------------------

def run_strategy(config=StrategyConfig()):
    """Run TOC chip bottleneck strategy via unified BacktestEngine."""
    # Always load from 2010-01-01 for proper factor warmup
    close, volume, amount = load_price_panels("2010-01-01")
    prices = PricePanel(close=close, volume=volume, amount=amount)
    
    raw = load_raw_close(start="2010-01-01")
    if not raw.empty:
        raw_aligned = raw.reindex(index=close.index, columns=close.columns)
        prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_aligned)

    # Load ROE panel for filtering
    codes = list(close.columns)
    fina = load_fina_indicator_panel(close.index, codes=codes, fields=["roe"])
    roe_panel = fina["roe"].shift(1)

    factor = build_factor(close, close.index, accel_diff=config.accel_diff)
    timing, tech_nav, timing_dist = build_timing(close, amount, ma_window=16)
    scheduled = build_rebalance_weights(
        factor, close, amount, roe_panel, config.top_n, config.rebalance_days, roe_thresh=config.roe_threshold
    )

    engine_config = BacktestConfig(
        start=config.start,
        cost=CostModel(
            buy_cost=config.cost.buy_cost,
            sell_cost=config.cost.sell_cost,
            financing_rate=config.cost.financing_rate,
        ),
        leverage=config.leverage,
    )
    engine = BacktestEngine(prices=prices, config=engine_config)
    signal = Signal(
        weights=scheduled,
        timing=timing,
        family=config.family,
        version=config.version,
    )
    result = engine.run(signal)

    # Truncate returned factor/timing/weights to starting date for analysis alignment
    start_dt = pd.Timestamp(config.start)
    factor_trunc = factor.loc[start_dt:]
    timing_trunc = timing.loc[start_dt:]
    scheduled_trunc = {k: v for k, v in scheduled.items() if k >= start_dt}

    return {
        "close": close.loc[start_dt:],
        "volume": volume.loc[start_dt:],
        "amount": amount.loc[start_dt:],
        "factor": factor_trunc,
        "timing": timing_trunc,
        "timing_dist": timing_dist.loc[start_dt:],
        "scheduled_weights": scheduled_trunc,
        "returns": result.returns,
        "detail": result.detail,
        "engine_result": result,
    }
