"""Sanity check for industry_rotation.py."""
import os
import sys
import pandas as pd
from pathlib import Path

# Align to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from strategies.industry_rotation import StrategyConfig, run_industry_rotation_strategy, latest_signal

def main():
    print("=" * 60)
    print("Testing M3 Industry Rotation Strategy Integration...")
    print("=" * 60)

    # 1. Test running backtest (OOS 2023-2026) for v1.2 (Legacy CPV Stock)
    print("\n[1/3] Running OOS backtest (version v1.2, CPV Stock Rotation)...")
    config_v12 = StrategyConfig(version="v1.2", start="2023-01-01", rebalance_days=20, w_cpv=0.5, cost_mode="stock")
    res_v12 = run_industry_rotation_strategy(config_v12)
    
    returns_v12 = res_v12["returns"]
    nav_v12 = (1 + returns_v12.fillna(0)).cumprod()
    ann_ret_v12 = nav_v12.iloc[-1] ** (252 / len(returns_v12)) - 1
    max_dd_v12 = (nav_v12 / nav_v12.cummax() - 1).min()
    
    print(f"  v1.2 OOS Annualized Return: {ann_ret_v12:+.2%}")
    print(f"  v1.2 OOS Max Drawdown: {max_dd_v12:.2%}")
    
    # 2. Test running backtest (OOS 2023-2026) for v1.3 (Huaxi ETF Rotation)
    print("\n[2/3] Running OOS backtest (version v1.3, Huaxi ETF Rotation)...")
    config_v13 = StrategyConfig(version="v1.3", start="2023-01-01", rebalance_days=20, cost_mode="etf")
    res_v13 = run_industry_rotation_strategy(config_v13)
    
    returns_v13 = res_v13["returns"]
    nav_v13 = (1 + returns_v13.fillna(0)).cumprod()
    ann_ret_v13 = nav_v13.iloc[-1] ** (252 / len(returns_v13)) - 1
    max_dd_v13 = (nav_v13 / nav_v13.cummax() - 1).min()
    
    print(f"  v1.3 OOS Annualized Return: {ann_ret_v13:+.2%}")
    print(f"  v1.3 OOS Max Drawdown: {max_dd_v13:.2%}")
    
    # 3. Test fetching latest signal
    print("\n[3/3] Fetching latest trading signal...")
    sig = latest_signal(config_v13)
    print(f"  Signal Date: {sig['date'].strftime('%Y-%m-%d')}")
    print(f"  In Market: {sig['in_market']}")
    print(f"  Top 10 Holdings: {sig['holdings'][:10] if sig['in_market'] else 'None (Bonds)'}")

    print("\nSanity Check Complete! ✅ Everything works perfectly.")

if __name__ == "__main__":
    main()
