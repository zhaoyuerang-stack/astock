"""Research Script: Backtesting the Optimized Multi-Strategy Portfolio.

Evaluates if blending M1 (Size baseline), M2 (Upgraded Adaptive CPV), and
M3 (Upgraded CPV Stock Selection) yields superior Sharpe and Calmar ratios.
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd

# Align to project root
PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.small_cap import StrategyConfig as SmallConfig, run_small_cap_strategy
from strategies.large_cap import StrategyConfig as LargeConfig, run_large_cap_strategy
from strategies.industry_rotation import StrategyConfig as IndConfig, run_industry_rotation_strategy

# Helper: Metrics
def get_metrics(ret):
    if len(ret) == 0:
        return {"annual": 0.0, "sharpe": 0.0, "maxdd": 0.0, "calmar": 0.0}
    nav = (1 + ret.fillna(0)).cumprod()
    ann = nav.iloc[-1] ** (252 / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    maxdd = float((nav / nav.cummax() - 1).min())
    calmar = ann / abs(maxdd) if maxdd != 0 else 0.0
    return {"annual": ann, "sharpe": sharpe, "maxdd": maxdd, "calmar": calmar}

def main():
    print("=" * 80)
    print("  PORTFOLIO OPTIMIZATION: UPGRADED M1 + M2 + M3 MULTI-STRATEGY PORTFOLIO  ")
    print("=" * 80)

    # 1. Run M1 (Small-cap Size v2.0 - Baseline)
    print("\n[1/3] Running M1 Small-cap Size v2.0 baseline...", flush=True)
    cfg_small = SmallConfig(start="2010-01-01")
    res_small = run_small_cap_strategy(cfg_small)
    r_m1 = res_small["returns"]

    # 2. Run M2 (Large-cap Growth Hedged v1.1 - Upgraded with Adaptive CPV)
    print("\n[2/3] Running M2 Large-cap Hedged v1.1 (Upgraded)...", flush=True)
    cfg_large = LargeConfig(start="2010-01-01", w_cpv_max=0.5)
    res_large = run_large_cap_strategy(cfg_large)
    r_m2 = res_large["returns"]

    # 3. Run M3 (Industry Neglect Rotation v1.2 - Upgraded with CPV Stock Selection)
    print("\n[3/3] Running M3 Industry Rotation v1.2 (Upgraded)...", flush=True)
    cfg_ind = IndConfig(start="2010-01-01", version="v1.2", w_cpv=0.5, cost_mode="stock")
    res_ind = run_industry_rotation_strategy(cfg_ind)
    r_m3 = res_ind["returns"]

    # Align dates
    common_idx = r_m1.index.intersection(r_m2.index).intersection(r_m3.index)
    ret_m1 = r_m1.loc[common_idx]
    ret_m2 = r_m2.loc[common_idx]
    ret_m3 = r_m3.loc[common_idx]

    print(f"  Aligned date range: {common_idx[0].date()} to {common_idx[-1].date()} ({len(common_idx)} days)")

    # Grid search over allocations (10% increments)
    weights = []
    for w1 in range(0, 11):
        for w2 in range(0, 11 - w1):
            w3 = 10 - w1 - w2
            weights.append((w1 / 10.0, w2 / 10.0, w3 / 10.0))

    sub_periods = [
        ("Full Period (2012-2026)", 2012),
        ("OOS Period (2023-2026)", 2023)
    ]

    for label, start_yr in sub_periods:
        print("\n" + "=" * 120)
        print(f"  Evaluation Period: {label}")
        print("=" * 120)
        print(f"{'M1 (Small)%':<11} | {'M2 (Hedged)%':<12} | {'M3 (Rot)%':<9} | {'Ann. Return':<12} | {'Sharpe':<7} | {'Max DD':<10} | {'Calmar Ratio':<12}")
        print("-" * 120)
        
        m1_s = ret_m1[ret_m1.index.year >= start_yr]
        m2_s = ret_m2[ret_m2.index.year >= start_yr]
        m3_s = ret_m3[ret_m3.index.year >= start_yr]
        
        comb_results = []
        for w1, w2, w3 in weights:
            r_comb = w1 * m1_s + w2 * m2_s + w3 * m3_s
            m = get_metrics(r_comb)
            comb_results.append((w1, w2, w3, m))
            
        # Sort by Sharpe descending
        comb_results.sort(key=lambda x: x[3]["sharpe"], reverse=True)
        
        print("Pure Standalone Strategies:")
        for w1, w2, w3, m in comb_results:
            if (w1 == 1.0) or (w2 == 1.0) or (w3 == 1.0):
                lbl = " (Pure M1)" if w1 == 1.0 else " (Pure M2)" if w2 == 1.0 else " (Pure M3)"
                print(f"{w1:>10.0%} | {w2:>11.0%} | {w3:>8.0%} | {m['annual']:>11.2%} | {m['sharpe']:>7.2f} | {m['maxdd']:>10.2%} | {m['calmar']:>12.2f}{lbl}")
        print("-" * 120)
        
        print("Top Optimal Blends (Sorted by Sharpe):")
        printed = 0
        for w1, w2, w3, m in comb_results:
            if w1 < 1.0 and w2 < 1.0 and w3 < 1.0:
                print(f"{w1:>10.0%} | {w2:>11.0%} | {w3:>8.0%} | {m['annual']:>11.2%} | {m['sharpe']:>7.2f} | {m['maxdd']:>10.2%} | {m['calmar']:>12.2f}")
                printed += 1
                if printed >= 8:
                    break
        print("=" * 120)

if __name__ == "__main__":
    main()
