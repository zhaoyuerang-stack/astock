"""Research Script: Applying CPV to Small-Cap Strategy (M1).

Tests if CPV can filter out bubble small-caps and select quiet/capitulated
micro-caps, boosting returns and lowering drawdowns.
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd

# Align to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.small_cap import load_price_panels, build_rebalance_weights, StrategyConfig as SmallConfig
from factors.small_cap import small_cap_timing

# Helper: Vectorized Correlation
def vectorized_rolling_corr(df1, df2, window=20):
    mean1 = df1.rolling(window).mean()
    mean2 = df2.rolling(window).mean()
    mean_prod = (df1 * df2).rolling(window).mean()
    cov = mean_prod - mean1 * mean2
    std1 = df1.rolling(window).std()
    std2 = df2.rolling(window).std()
    return cov / (std1 * std2 + 1e-8)

# Helper: Metrics
def get_metrics(ret):
    if len(ret) == 0:
        return {"annual": 0.0, "sharpe": 0.0, "maxdd": 0.0}
    nav = (1 + ret.fillna(0)).cumprod()
    ann = nav.iloc[-1] ** (252 / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    maxdd = float((nav / nav.cummax() - 1).min())
    return {"annual": ann, "sharpe": sharpe, "maxdd": maxdd}

def main():
    print("=" * 80)
    print("  RESEARCH: ENHANCING M1 SMALL-CAP STRATEGY WITH CPV REVERSAL  ")
    print("=" * 80)

    # 1. Load Data
    print("\n[1/3] Loading small-cap prices and amounts...", flush=True)
    close, volume, amount = load_price_panels("2010-01-01")
    raw_close = close.copy() # fallback raw close
    
    # Exclude corrupted dates
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    
    prices = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=close)

    # 2. Compute Factors
    print("\n[2/3] Computing Size and CPV factors...", flush=True)
    # Size factor: rolling 60-day mean of amount (smaller amount = smaller cap)
    size = amount.rolling(60).mean()
    size_r = size.rank(axis=1, pct=True, na_option="bottom") # Small size gets low rank
    
    # CPV factor
    cpv = vectorized_rolling_corr(close, amount, window=20)
    cpv_r = cpv.rank(axis=1, pct=True, na_option="bottom") # Low CPV gets low rank

    # 3. Construct Strategy Variants
    # Baseline Size60 factor (smaller is better, so rank factor = -size_r)
    f_baseline = -size_r
    
    # Variant A: Size + CPV Rank Penalty
    # We want low size and low CPV, so we minimize (size_r + 0.5 * cpv_r)
    # To use nlargest in build_rebalance_weights, we negate it:
    f_penalty_03 = -(size_r + 0.3 * cpv_r)
    f_penalty_05 = -(size_r + 0.5 * cpv_r)
    f_penalty_10 = -(size_r + 1.0 * cpv_r)
    
    # Variant B: Quiet Filter
    # Select top 100 smallest stocks, then select top 25 with lowest CPV
    # We can represent this factor by penalizing stocks with CPV > median
    cpv_median = cpv.median(axis=1)
    quiet_mask = cpv.le(cpv_median, axis=0)
    f_quiet_filter = -size_r.where(quiet_mask)

    # 4. Run Backtests
    print("\n[3/3] Simulating M1 variants (using MA16 timing)...", flush=True)
    timing, small_nav, timing_dist = small_cap_timing(close, amount, 16)
    
    # Common Cost Model (0.47% friction, 6.5% borrow rate, 1.25x leverage)
    costs = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.065)
    config = BacktestConfig(start="2010-01-01", cost=costs, leverage=1.25)

    def run_m1_variant(factor):
        scheduled = build_rebalance_weights(factor, close, top_n=25, rebalance_days=20)
        engine = BacktestEngine(prices=prices, config=config)
        signal = Signal(weights=scheduled, timing=timing)
        res = engine.run(signal)
        return res.returns

    ret_base = run_m1_variant(f_baseline)
    ret_pen03 = run_m1_variant(f_penalty_03)
    ret_pen05 = run_m1_variant(f_penalty_05)
    ret_pen10 = run_m1_variant(f_penalty_10)
    ret_qfilt = run_m1_variant(f_quiet_filter)

    # 5. Compare Results
    for label, start_yr in [("Full Period (2012-2026)", 2012), ("OOS Period (2023-2026)", 2023)]:
        print("\n" + "=" * 95)
        print(f"  SMALL-CAP CPV ENHANCEMENT MATRIX: {label}")
        print("=" * 95)
        print(f"{'Strategy Variant':<45} | {'Annual Return':<13} | {'Sharpe':<7} | {'Max Drawdown':<12}")
        print("-" * 95)
        
        for name, ret in [
            ("M1 Baseline (Size60)", ret_base),
            ("M1 + CPV Rank Penalty (w=0.3)", ret_pen03),
            ("M1 + CPV Rank Penalty (w=0.5)", ret_pen05),
            ("M1 + CPV Rank Penalty (w=1.0)", ret_pen10),
            ("M1 + Quiet CPV Filter (CPV <= median)", ret_qfilt)
        ]:
            r_slice = ret[ret.index.year >= start_yr]
            m = get_metrics(r_slice)
            print(f"{name:<45} | {m['annual']:>13.2%} | {m['sharpe']:>7.2f} | {m['maxdd']:>12.2%}")
        print("=" * 95)

if __name__ == "__main__":
    main()
