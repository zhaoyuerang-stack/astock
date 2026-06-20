"""Diagnostics script to debug factor differences for different w.
"""
import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from factors.large_cap import load_clean_panels_with_growth, build_universe
from strategies.small_cap import build_rebalance_weights

def vectorized_rolling_corr(df1, df2, window=20):
    mean1 = df1.rolling(window).mean()
    mean2 = df2.rolling(window).mean()
    mean_prod = (df1 * df2).rolling(window).mean()
    cov = mean_prod - mean1 * mean2
    std1 = df1.rolling(window).std()
    std2 = df2.rolling(window).std()
    return cov / (std1 * std2 + 1e-8)

def main():
    panels = load_clean_panels_with_growth()
    close = panels["close"]
    amount = panels["amount"]
    
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    
    univ = build_universe(panels, 200).reindex(clean_dates)
    
    pe = panels["pe"].reindex(clean_dates)
    pb = panels["pb"].reindex(clean_dates)
    roe = panels["roe"].reindex(clean_dates)
    npy = panels["npy"].reindex(clean_dates)
    
    pe_r = pe.rank(axis=1, pct=True, na_option="bottom")
    pb_r = pb.rank(axis=1, pct=True, na_option="bottom")
    val_r = (pe_r + pb_r) / 2.0
    roe_r = roe.rank(axis=1, pct=True, na_option="bottom")
    npy_r = npy.rank(axis=1, pct=True, na_option="bottom")
    grow_r = (roe_r + npy_r) / 2.0
    
    cpv = vectorized_rolling_corr(close, amount, window=20)
    cpv_raw_r = cpv.rank(axis=1, pct=True, na_option="bottom")
    m_liq = 1.0 / (amount.rolling(20).mean() + 1.0)
    m_liq_r = m_liq.rank(axis=1, pct=True, na_option="bottom")
    cpv_r = (cpv_raw_r * m_liq_r).rank(axis=1, pct=True, na_option="bottom")
    
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()
            
    bench_nav = (1 + bench_returns).cumprod()
    bench_ma = bench_nav.rolling(120).mean()
    is_bull = (bench_nav > bench_ma).astype(float).shift(1).fillna(0.0)
    
    print("Regime breakdown (is_bull):")
    print(is_bull.value_counts(dropna=False))
    
    is_bull_df = pd.DataFrame({col: is_bull for col in close.columns}, index=close.index)
    
    w_candidates = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]
    factors = {}
    for w in w_candidates:
        w_cpv = is_bull_df * w
        factors[w] = ((val_r + grow_r - w_cpv * cpv_r) / (2.0 + w_cpv)).where(univ)
        
    print("\nChecking factor values on a specific date in a bull regime:")
    bull_dates = is_bull[is_bull == 1.0].index
    if len(bull_dates) > 100:
        test_dt = bull_dates[100]
        print(f"Date: {test_dt}")
        for w in w_candidates:
            f_vals = factors[w].loc[test_dt].dropna()
            print(f"w = {w:.2f}: sum = {f_vals.sum():.4f}, mean = {f_vals.mean():.4f}, std = {f_vals.std():.4f}")
            # print top 5 stocks
            top_5 = f_vals.nlargest(5)
            print(f"  Top 5 stocks: {list(top_5.index)}")
            print(f"  Top 5 values: {list(top_5.values)}")
            
        print("\nComparing rebalance weights for w=0.25 vs other candidates:")
        sched_025 = build_rebalance_weights(factors[0.25], close, 25, 40)
        for w in [0.5, 0.75, 1.0, 1.5]:
            sched_other = build_rebalance_weights(factors[w], close, 25, 40)
            common_dates = set(sched_025.keys()).intersection(sched_other.keys())
            diff_count = 0
            for dt in sorted(common_dates):
                s1 = set(sched_025[dt].index)
                s2 = set(sched_other[dt].index)
                if s1 != s2:
                    diff_count += 1
            print(f"w = {w:.2f}: {diff_count} / {len(common_dates)} rebalance dates have different holdings compared to w=0.25")

if __name__ == "__main__":
    main()

