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
    
    factor = res["factor"]
    scheduled = res["scheduled_weights"]
    close = res["close"]
    
    print("Factor DataFrame Shape:", factor.shape)
    print("Number of non-NaN elements in factor:", factor.notna().sum().sum())
    
    print("\nScheduled Weights Keys (first 10):")
    print(list(scheduled.keys())[:10])
    print("\nScheduled Weights Length:", len(scheduled))
    
    if scheduled:
        first_key = list(scheduled.keys())[0]
        print(f"\nWeights for {first_key}:")
        print(scheduled[first_key])

if __name__ == "__main__":
    main()
