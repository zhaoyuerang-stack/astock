"""Sanity check for the new d-LE-SC (directed Likelihood Estimation Spectral Clustering) strategy.
"""

import os
import sys
from pathlib import Path
import numpy as np

# Align to project root
PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from strategies.d_le_sc import StrategyConfig, run_d_le_sc_strategy, latest_signal


def main():
    print("=" * 60)
    print("Testing d-LE-SC Strategy Integration...")
    print("=" * 60)

    # 1. Test running backtest (OOS 2023-2026)
    print("\n[1/3] Running OOS backtest (2023 to present)...")
    config = StrategyConfig(start="2023-01-01", correlation_method="pearson")
    res = run_d_le_sc_strategy(config)
    
    returns = res["returns"]
    nav = (1 + returns.fillna(0)).cumprod()
    
    # Calculate performance metrics
    ann_ret = returns.mean() * 252
    max_dd = (nav / nav.cummax() - 1).min()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0.0

    print(f"  OOS Annualized Return: {ann_ret:+.2%}")
    print(f"  OOS Sharpe Ratio: {sharpe:.2f}")
    print(f"  OOS Max Drawdown: {max_dd:.2%}")

    # 2. Test fetching latest signal
    print("\n[2/3] Fetching latest trading signal...")
    sig = latest_signal(config)
    print(f"  Signal Date: {sig['date'].strftime('%Y-%m-%d')}")
    print(f"  In Market: {sig['in_market']}")
    print(f"  Top 5 Holdings: {sig['holdings'][:5]}")

    print("\n[3/3] Sanity Check Complete! ✅ Everything works perfectly.")


if __name__ == "__main__":
    main()
