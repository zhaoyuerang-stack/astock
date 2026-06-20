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

def main():
    config = StrategyConfig(
        start="2012-01-01",
        network_type="overnight_lead_daytime",
        correlation_method="pearson",
        rebalance_days=20
    )
    res = run_d_le_sc_strategy(config)
    
    r_neutral = res["returns"]
    r_long = res["long_returns"]
    r_bench = res["bench_returns"]
    
    print("Full History (2012-2026) Performance:")
    print(f"  Long Portfolio Ann Return: {r_long.mean() * 252:+.2%}")
    print(f"  Long Portfolio Sharpe:     {r_long.mean() / r_long.std() * np.sqrt(252):.2f}")
    print(f"  Long Portfolio Volatility: {r_long.std() * np.sqrt(252):.2%}")
    print(f"  Long Portfolio Max DD:     {((1 + r_long).cumprod() / (1 + r_long).cumprod().cummax() - 1).min():.2%}")
    print()
    print(f"  Benchmark Ann Return:      {r_bench.mean() * 252:+.2%}")
    print(f"  Benchmark Sharpe:          {r_bench.mean() / r_bench.std() * np.sqrt(252):.2f}")
    print(f"  Benchmark Max DD:          {((1 + r_bench).cumprod() / (1 + r_bench).cumprod().cummax() - 1).min():.2%}")
    print()
    print(f"  Hedged Ann Return:         {r_neutral.mean() * 252:+.2%}")
    print(f"  Hedged Sharpe:             {r_neutral.mean() / r_neutral.std() * np.sqrt(252):.2f}")
    print(f"  Hedged Max DD:             {((1 + r_neutral).cumprod() / (1 + r_neutral).cumprod().cummax() - 1).min():.2%}")

if __name__ == "__main__":
    main()
