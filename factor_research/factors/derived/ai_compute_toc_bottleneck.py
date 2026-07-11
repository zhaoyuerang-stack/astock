"""Theory of Constraints (TOC) chip bottleneck factor.

Restricts universe to ChiNext & STAR market tech boards,
computes the second derivative of gross profit margin YoY (acceleration),
and filters by ROE > 6%.
"""
import numpy as np
import pandas as pd
from factors.utils import safe_zscore, mad_clip
from lake.load_lake import load_prices, load_raw_close, load_fina_indicator_panel

def ai_compute_toc_bottleneck_factor(close, amount=None):
    """
    TOC Chip/AI Compute Bottleneck factor.
    Returns: date x code DataFrame of factor values (z-scored).
    """
    trade_dates = close.index
    codes = list(close.columns)
    
    # 1. Load financials (gross profit margin and roe)
    # Aligned on ann_date and ffilled to trade dates
    fina = load_fina_indicator_panel(trade_dates, codes=codes, fields=["grossprofit_margin", "roe"])
    margin_panel = fina["grossprofit_margin"].shift(1)  # shift 1 day to prevent look-ahead
    roe_panel = fina["roe"].shift(1)
    
    # 2. Build tech boards universe mask (ChiNext: 30*, STAR: 688*)
    tech_mask = pd.Series(codes, index=codes).str.startswith("30") | \
                pd.Series(codes, index=codes).str.startswith("688")
    
    # Liquidity mask (top 500 by 20-day mean amount)
    if amount is not None:
        avg_amount = amount.rolling(20).mean()
    else:
        # Fallback if amount is not provided: load from data lake
        _, _, amount_loaded = _load_price_panels_internal(trade_dates.min())
        avg_amount = amount_loaded.reindex(index=trade_dates, columns=codes).rolling(20).mean()
        
    # Rank columns horizontally within the tech board pool
    tech_amount = avg_amount.loc[:, tech_mask]
    liq_rank = tech_amount.rank(axis=1, ascending=False)
    
    # Full universe mask: top 500 liquidity tech stocks
    universe_mask = (liq_rank <= 500).reindex(columns=codes, fill_value=False) & close.notna()
    
    # 3. Factor calculation: margin YoY acceleration
    margin_yoy = margin_panel.diff(250)
    margin_accel = margin_yoy.diff(63).replace(0.0, np.nan).ffill()
    
    # ROE filter
    roe_mask = roe_panel > 6.0
    
    # Combined factor signal
    raw_factor = margin_accel.where(universe_mask & roe_mask)
    
    # Standardize
    return safe_zscore(mad_clip(raw_factor))


def _load_price_panels_internal(start):
    from lake.load_lake import load_prices, load_raw_close
    px = load_prices(start=start, fields=("close", "volume"))
    raw = load_raw_close(start=start)
    amount = px["volume"] * 100 * raw.reindex(index=px["volume"].index, columns=px["volume"].columns)
    close, volume = px["close"], px["volume"]
    valid = amount.notna().sum(axis=1)
    if len(valid) > 5:
        typical = valid.iloc[-60:].median()
        good = valid[valid >= typical * 0.7]
        if len(good):
            cutoff = good.index[-1]
            close, volume, amount = close.loc[:cutoff], volume.loc[:cutoff], amount.loc[:cutoff]
    return close, volume, amount
