import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Align to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from strategies.d_le_sc import StrategyConfig, run_d_le_sc_strategy

def run_sweep():
    network_types = ["overnight_lead_daytime", "daytime_lead_overnight", "preclose_lead_close"]
    methods = ["pearson", "spearman"]
    rebalances = [5, 20]
    directions = [1, -1]  # 1 = standard, -1 = reversed

    print("=" * 110)
    print(f"{'Network Type':<26}{'Method':<10}{'Reb':<5}{'Dir':<5}{'Ann Return':<15}{'Sharpe':<10}{'Max DD':<10}")
    print("=" * 110)

    # We will temporarily intercept build_d_le_sc_factor to apply direction multiplier
    import factors.d_le_sc
    import strategies.d_le_sc
    original_build_factor = factors.d_le_sc.build_d_le_sc_factor

    for net_type in network_types:
        for method in methods:
            for reb in rebalances:
                for direction in directions:
                    # Mock function to inject direction multiplier
                    def mocked_build_factor(*args, **kwargs):
                        factor, univ = original_build_factor(*args, **kwargs)
                        return direction * factor, univ
                    
                    factors.d_le_sc.build_d_le_sc_factor = mocked_build_factor
                    strategies.d_le_sc.build_d_le_sc_factor = mocked_build_factor

                    config = StrategyConfig(
                        start="2023-01-01",
                        network_type=net_type,
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
                        
                        dir_str = "std" if direction == 1 else "rev"
                        print(f"{net_type:<26}{method:<10}{reb:<5}{dir_str:<5}{ann_ret:>13.2%}{sharpe:>10.2f}{max_dd:>10.2%}")
                    except Exception as e:
                        print(f"{net_type:<26}{method:<10}{reb:<5}{direction:<5} Error: {e}")

    # Restore original function
    factors.d_le_sc.build_d_le_sc_factor = original_build_factor
    strategies.d_le_sc.build_d_le_sc_factor = original_build_factor

if __name__ == "__main__":
    run_sweep()
