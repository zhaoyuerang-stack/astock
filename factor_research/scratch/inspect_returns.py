import os
import sys
from pathlib import Path

# Align to project root
PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from strategies.d_le_sc import StrategyConfig, run_d_le_sc_strategy

def main():
    config = StrategyConfig(start="2023-01-01")
    res = run_d_le_sc_strategy(config)
    
    r_neutral = res["returns"]
    r_long = res["long_returns"]
    r_bench = res["bench_returns"]
    
    print("Neutral Returns Head:")
    print(r_neutral.head(10))
    print("\nNeutral Returns Tail:")
    print(r_neutral.tail(10))
    
    print("\nLong Returns Summary:")
    print(r_long.describe())
    
    print("\nBench Returns Summary:")
    print(r_bench.describe())
    
    print("\nChecking any extreme values in Long Returns:")
    print(r_long[r_long.abs() > 0.5])
    
    print("\nChecking any extreme values in Bench Returns:")
    print(r_bench[r_bench.abs() > 0.5])

if __name__ == "__main__":
    main()
