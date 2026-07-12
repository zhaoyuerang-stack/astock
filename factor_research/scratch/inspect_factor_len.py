import os
import sys
from pathlib import Path

# Align to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
    factor = res["factor"]
    close = res["close"]
    
    fdates = factor.dropna(how="all").index.intersection(close.index)
    print(f"Total fdates: {len(fdates)}")
    
    skipped = 0
    valid_lens = []
    for rd in fdates:
        f = factor.loc[rd].dropna()
        active = close.loc[rd].dropna().index
        f = f.reindex(active).dropna()
        valid_lens.append(len(f))
        if len(f) < config.top_n:
            skipped += 1
            
    print(f"Skipped days: {skipped} out of {len(fdates)}")
    print("Distribution of factor lengths on rebalance days:")
    print(pd.Series(valid_lens).describe())

if __name__ == "__main__":
    main()
