import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Align to project root
PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from strategies.d_le_sc import StrategyConfig, run_d_le_sc_strategy

def run_sweep():
    # Define parameter grid
    lookbacks = [60, 120]
    methods = ["pearson", "spearman"]
    rebalances = [1, 5, 10, 20]

    results = []

    print("=" * 80)
    print(f"{'Lookback':<10}{'Method':<10}{'Rebalance':<10}{'Annual Return':<15}{'Sharpe':<10}{'Max DD':<10}")
    print("=" * 80)

    for lb in lookbacks:
        for method in methods:
            for reb in rebalances:
                config = StrategyConfig(
                    start="2023-01-01",
                    lookback=lb,
                    correlation_method=method,
                    rebalance_days=reb
                )
                try:
                    res = run_d_le_sc_strategy(config)
                    returns = res["returns"]
                    nav = (1 + returns.fillna(0)).cumprod()
                    ann_ret = returns.mean() * 252
                    max_dd = (nav / nav.cummax() - 1).min()
                    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0.0
                    
                    print(f"{lb:<10}{method:<10}{reb:<10}{ann_ret:>13.2%}{sharpe:>10.2f}{max_dd:>10.2%}")
                    results.append({
                        "lookback": lb,
                        "method": method,
                        "rebalance": reb,
                        "ann_ret": ann_ret,
                        "sharpe": sharpe,
                        "max_dd": max_dd
                    })
                except Exception as e:
                    print(f"{lb:<10}{method:<10}{reb:<10} Error: {e}")

if __name__ == "__main__":
    run_sweep()
