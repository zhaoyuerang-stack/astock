"""
Compare GA searches using Default Fitness vs Regime-Aware Min-Max Fitness.
Also computes the drawdown and performance of both top champions under the crash regime.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
from strategies.small_cap import load_price_panels
from governance.holdout import boundary
from factory.autoresearch.islands import run_island_search

def run_experiment():
    b = boundary()
    print(f"[*] Holdout boundary: {b}")
    close, volume, amount = load_price_panels("2022-01-01")
    # Strictly isolate from holdout
    close = close[close.index < b]
    volume = volume[volume.index < b]
    amount = amount[amount.index < b]
    # We want a 20-day horizon forward return
    forward_ret = close.shift(-20) / close - 1.0

    print("=== Running GA Search with Default Fitness ===")
    res_default = run_island_search(
        close, volume, amount, forward_ret,
        vintage_id="compare-regimes-default",
        n_islands=2, generations=2, population=4, elite=1, top_k=3,
        final_stage="l0", seeds=None, rng_seed=42, sample_dates=120,
        novelty_weight=0.0, corr_weight=0.0, turnover_weight=0.0,
        regime_aware=False
    )

    print("\n=== Running GA Search with Regime-Aware Min-Max Fitness ===")
    res_regime = run_island_search(
        close, volume, amount, forward_ret,
        vintage_id="compare-regimes-regime",
        n_islands=2, generations=2, population=4, elite=1, top_k=3,
        final_stage="l0", seeds=None, rng_seed=42, sample_dates=120,
        novelty_weight=0.0, corr_weight=0.0, turnover_weight=0.0,
        regime_aware=True
    )

    # Output details of both champions
    print("\n=== Default Fitness Champions ===")
    for idx, c in enumerate(res_default.champions):
        print(f"Rank {idx+1}: {c.expr}")
        print(f"  Global Raw ICIR: {c.icir:.4f}")
        print(f"  Fitness Score: {c.fitness:.4f}")
        print(f"  Regime 1 (Small-cap Crash): {c.regime_icirs.get('regime_1', 0.0):.4f}")
        print(f"  Regime 2 (Value/Large-cap Rotation): {c.regime_icirs.get('regime_2', 0.0):.4f}")
        print(f"  Regime 3 (Normal/Bull Market): {c.regime_icirs.get('regime_3', 0.0):.4f}")

    print("\n=== Regime-Aware Fitness Champions ===")
    for idx, c in enumerate(res_regime.champions):
        print(f"Rank {idx+1}: {c.expr}")
        print(f"  Global Raw ICIR: {c.icir:.4f}")
        print(f"  Fitness Score: {c.fitness:.4f}")
        print(f"  Regime 1 (Small-cap Crash): {c.regime_icirs.get('regime_1', 0.0):.4f}")
        print(f"  Regime 2 (Value/Large-cap Rotation): {c.regime_icirs.get('regime_2', 0.0):.4f}")
        print(f"  Regime 3 (Normal/Bull Market): {c.regime_icirs.get('regime_3', 0.0):.4f}")

    # Now let's calculate drawdown and performance of both top champions under the crash regime
    # Regime 1: 2024-01-02 to 2024-02-08
    from factors.autoresearch_dsl import compute_dsl_factor
    from factory.autoresearch.novelty import topn_long_return

    crash_start = "2024-01-02"
    crash_end = "2024-02-08"
    
    # 1-day forward return: buying at T close and selling at T+1 close
    daily_forward_ret = close.pct_change(1).shift(-1)

    def analyze_champion(champ, label):
        panel = compute_dsl_factor(close, volume, ast=champ.ast)
        # Compute top-N long daily returns series
        ret_series = topn_long_return(panel, daily_forward_ret, 25)
        # Slice for the crash regime
        crash_ret = ret_series.loc[crash_start:crash_end]
        
        # Cumulative return
        cum_ret = (1.0 + crash_ret).prod() - 1.0
        
        # Maximum drawdown
        cum_equity = (1.0 + crash_ret).cumprod()
        running_max = cum_equity.cummax()
        drawdown = (cum_equity - running_max) / running_max
        max_dd = drawdown.min()
        
        print(f"\n[{label} Champion Performance under Crash Regime ({crash_start} to {crash_end})]")
        print(f"  Expr: {champ.expr}")
        print(f"  Cumulative Return: {cum_ret:.4%}")
        print(f"  Max Drawdown: {max_dd:.4%}")
        return cum_ret, max_dd

    if res_default.champions:
        analyze_champion(res_default.champions[0], "Default")
    if res_regime.champions:
        analyze_champion(res_regime.champions[0], "Regime-Aware")

if __name__ == "__main__":
    run_experiment()
