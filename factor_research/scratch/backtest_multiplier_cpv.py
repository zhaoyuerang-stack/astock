"""Quantitative Research Script: Testing Multiplier-Weighted CPV Factors.

Evaluates the theoretical formula P = M * f by weighting the CPV factor
with liquidity and size multipliers, and compares the IC and quintile returns
against the raw CPV baseline.
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
from factors.large_cap import load_clean_panels_with_growth

# Vectorized Rolling Correlation Helper
def vectorized_rolling_corr(df1, df2, window=20):
    mean1 = df1.rolling(window).mean()
    mean2 = df2.rolling(window).mean()
    mean_prod = (df1 * df2).rolling(window).mean()
    cov = mean_prod - mean1 * mean2
    std1 = df1.rolling(window).std()
    std2 = df2.rolling(window).std()
    return cov / (std1 * std2 + 1e-8)

# Performance Metrics Helper
def get_metrics(ret):
    if len(ret) == 0:
        return {"annual": 0.0, "sharpe": 0.0, "maxdd": 0.0}
    nav = (1 + ret.fillna(0)).cumprod()
    ann = nav.iloc[-1] ** (252 / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    maxdd = float((nav / nav.cummax() - 1).min())
    return {"annual": ann, "sharpe": sharpe, "maxdd": maxdd}

def main():
    print("=" * 85)
    print("  QUANTITATIVE BACKTEST: MULTIPLIER-WEIGHTED CPV FACTORS  ")
    print("=" * 85)

    # 1. Load Data
    print("\n[1/4] Loading and cleaning panels...", flush=True)
    panels = load_clean_panels_with_growth()
    close = panels["close"]
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    raw_close = raw_close.reindex(clean_dates)
    
    prices = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=raw_close)

    # Define the Top 200 Large-Cap Universe
    cap = amount.rolling(20).mean() * raw_close
    univ = cap.rank(axis=1, ascending=False, pct=False) <= 200

    # 2. Compute Factors
    print("\n[2/4] Computing Multiplier and CPV factors...", flush=True)
    
    # Raw CPV20
    cpv = vectorized_rolling_corr(close, amount, window=20)
    
    # Multiplier 1: Liquidity Multiplier (M_liq = 1 / average trade amount)
    avg_amt = amount.rolling(20).mean()
    m_liq = 1.0 / (avg_amt + 1.0) # Add 1 to prevent division by zero
    
    # Multiplier 2: Size Multiplier (M_cap = 1 / market cap proxy)
    m_cap = 1.0 / (cap + 1.0)
    
    # Define Factor Configurations to test
    # We filter them to the universe first to ensure correct ranks
    factors = {
        "Raw CPV (Baseline)": cpv.where(univ),
        "CPV * M_liq (Liquidity weighted)": (cpv * m_liq).where(univ),
        "CPV * M_cap (Size weighted)": (cpv * m_cap).where(univ),
        "CPV_rank * M_liq_rank (Rank product)": (cpv.rank(axis=1, pct=True) * m_liq.rank(axis=1, pct=True)).where(univ)
    }

    # 3. Information Coefficient (IC) Analysis
    print("\n[3/4] Running 5-day Forward IC/ICIR analysis...", flush=True)
    fwd_ret_5d = close.pct_change(5).shift(-5)
    valid_dates = cpv.index[120:-5]
    
    ic_results = {}
    for name, f_panel in factors.items():
        ics = []
        for dt in valid_dates:
            f_val = f_panel.loc[dt].dropna()
            r_val = fwd_ret_5d.loc[dt].dropna()
            common = f_val.index.intersection(r_val.index)
            if len(common) > 50:
                ic = f_val.loc[common].corr(r_val.loc[common], method="spearman")
                ics.append(ic)
        ics_series = pd.Series(ics, index=valid_dates)
        mean_ic = ics_series.mean()
        ir = ics_series.mean() / ics_series.std() if ics_series.std() > 0 else 0.0
        ic_results[name] = {"mean_ic": mean_ic, "icir": ir}
        print(f"  {name:<40} | Mean IC: {mean_ic:+.4f} | ICIR: {ir:+.4f}")

    # 4. Quintile Backtests
    print("\n[4/4] Running Quintile Backtests...", flush=True)
    rebalance_days = 20
    rebal_dates = cpv.index[120::rebalance_days]
    costs = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)
    config = BacktestConfig(start="2012-01-01", cost=costs, leverage=1.0)
    
    backtest_results = {}
    
    for name, f_panel in factors.items():
        print(f"  Simulating quintiles for: {name}...", flush=True)
        weights_q1 = {}
        weights_q5 = {}
        
        for i in range(len(rebal_dates)):
            dt_current = rebal_dates[i]
            pos = close.index.get_loc(dt_current)
            if pos + 1 >= len(close.index):
                continue
            effective_date = close.index[pos + 1]
            
            f = f_panel.loc[dt_current].dropna()
            if len(f) < 40:
                continue
                
            q1_stocks = f.nsmallest(int(len(f) * 0.2)).index.tolist()
            q5_stocks = f.nlargest(int(len(f) * 0.2)).index.tolist()
            
            if len(q1_stocks) > 0:
                weights_q1[effective_date] = pd.Series(1.0 / len(q1_stocks), index=q1_stocks)
            if len(q5_stocks) > 0:
                weights_q5[effective_date] = pd.Series(1.0 / len(q5_stocks), index=q5_stocks)
                
        # Run Q1 and Q5
        engine_q1 = BacktestEngine(prices=prices, config=config)
        res_q1 = engine_q1.run(Signal(weights=weights_q1, timing=None))
        
        engine_q5 = BacktestEngine(prices=prices, config=config)
        res_q5 = engine_q5.run(Signal(weights=weights_q5, timing=None))
        
        backtest_results[name] = {"q1": res_q1.returns, "q5": res_q5.returns}

    # Reference Benchmark
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()

    # 5. Output comparison matrix
    for label, start_yr in [("Full Period (2012-2026)", 2012), ("OOS Period (2023-2026)", 2023)]:
        print("\n" + "=" * 115)
        print(f"  PORTFOLIO PERFORMANCE MATRIX: {label}")
        print("=" * 115)
        print(f"{'Factor Configuration':<40} | {'Portfolio':<6} | {'Annual Return':<13} | {'Sharpe':<7} | {'Max Drawdown':<12}")
        print("-" * 115)
        
        # Benchmark
        b_slice = bench_returns[bench_returns.index.year >= start_yr]
        m_bench = get_metrics(b_slice)
        print(f"{'Top 200 Benchmark':<40} | {'Index':<6} | {m_bench['annual']:>13.2%} | {m_bench['sharpe']:>7.2f} | {m_bench['maxdd']:>12.2%}")
        print("-" * 115)
        
        for name in factors.keys():
            res = backtest_results[name]
            
            # Q1
            q1_s = res["q1"][res["q1"].index.year >= start_yr]
            m_q1 = get_metrics(q1_s)
            print(f"{name:<40} | {'Q1':<6} | {m_q1['annual']:>13.2%} | {m_q1['sharpe']:>7.2f} | {m_q1['maxdd']:>12.2%}")
            
            # Q5
            q5_s = res["q5"][res["q5"].index.year >= start_yr]
            m_q5 = get_metrics(q5_s)
            print(f"{name:<40} | {'Q5':<6} | {m_q5['annual']:>13.2%} | {m_q5['sharpe']:>7.2f} | {m_q5['maxdd']:>12.2%}")
            
            # Long-Short Spread (Q1 is long since CPV has negative IC)
            # Reversing factor: Long Q1, Short Q5
            spread_s = q1_s - q5_s
            m_spread = get_metrics(spread_s)
            print(f"{name:<40} | {'Q1-Q5':<6} | {m_spread['annual']:>13.2%} | {m_spread['sharpe']:>7.2f} | {m_spread['maxdd']:>12.2%}")
            print("-" * 115)

if __name__ == "__main__":
    main()
