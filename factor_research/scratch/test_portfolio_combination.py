"""Comprehensive evaluation of portfolio combinations.
"""
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.chdir(Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(Path.cwd()))

import numpy as np
import pandas as pd

from portfolio.strategy_runners import LIVE_STRATEGIES
from portfolio.composer import compose, metrics as port_metrics
from portfolio.analysis import contribution_decompose, correlation_matrix
from strategies.industry_rotation import StrategyConfig, run_industry_rotation_strategy
from factors.small_cap import small_cap_timing
from portfolio.regime import classify


def run_industry_rotation_v1_3(start: str = "2018-01-01") -> pd.Series:
    cfg = StrategyConfig(version="v1.3", start=start, cost_mode="etf")
    res = run_industry_rotation_strategy(cfg)
    return res["returns"].dropna()


def main():
    print("=" * 80)
    print("  COMPREHENSIVE PORTFOLIO COMBINATION STUDY")
    print("=" * 80)

    start_date = "2018-01-01"

    # 1. Run/Load all candidates
    print("\n[1] Running and loading strategies...")
    r_sc = LIVE_STRATEGIES["small-cap-size.v2.0"]["fn"](start_date)
    r_illiq = LIVE_STRATEGIES["illiquidity.v1.0"]["fn"](start_date)
    r_bond = LIVE_STRATEGIES["gov_bond_etf_511010.MA60"]["fn"](start_date)
    r_ind = run_industry_rotation_v1_3(start_date)

    # Load shared regime signal (PureTrend MA16)
    from strategies.small_cap import load_price_panels
    close, _, amount = load_price_panels("2010-01-01")
    timing, _, timing_dist = small_cap_timing(close, amount, ma_window=16)
    regime_signal = timing.astype(float).loc[start_date:]

    # Define portfolios
    portfolios = {
        "A: Baseline (SC + Illiq)": {
            "small-cap-size.v2.0": r_sc,
            "illiquidity.v1.0": r_illiq,
        },
        "B: Baseline + Gov Bond": {
            "small-cap-size.v2.0": r_sc,
            "illiquidity.v1.0": r_illiq,
            "gov_bond_etf.MA60": r_bond,
        },
        "C: Baseline + Industry Rotation": {
            "small-cap-size.v2.0": r_sc,
            "illiquidity.v1.0": r_illiq,
            "industry-neglect.v1.3": r_ind,
        },
        "D: All 4 Strategies": {
            "small-cap-size.v2.0": r_sc,
            "illiquidity.v1.0": r_illiq,
            "industry-neglect.v1.3": r_ind,
            "gov_bond_etf.MA60": r_bond,
        }
    }

    # 2. Individual metrics
    print("\n[2] Individual Strategy Metrics:")
    for name, r in [("small-cap-size.v2.0", r_sc), ("illiquidity.v1.0", r_illiq),
                    ("industry-neglect.v1.3", r_ind), ("gov_bond_etf.MA60", r_bond)]:
        m = port_metrics(r)
        print(f"  {name:<25} | Ann: {m['annual']:+.2%} | Vol: {m['vol']:.2%} | Sharpe: {m['sharpe']:.2f} | MaxDD: {m['maxdd']:.2%} | Calmar: {m['calmar']:.2f}")

    # 3. Correlation matrix
    print("\n[3] Correlation Matrix (All 4 Candidates):")
    df_all = pd.DataFrame({
        "small-cap-size": r_sc,
        "illiquidity": r_illiq,
        "industry-neglect": r_ind,
        "gov_bond_etf": r_bond
    }).dropna()
    print(df_all.corr().round(3))

    # 4. Evaluation of Compositions
    print("\n[4] Portfolio Performance Comparison:")
    results = []

    for port_name, assets in portfolios.items():
        print(f"\n  Evaluating {port_name}:")
        for method in ["equal_weight", "risk_parity", "regime_adaptive"]:
            try:
                p_ret, w_hist = compose(assets, method=method, regime_signal=regime_signal)
                m = port_metrics(p_ret)
                results.append({
                    "portfolio": port_name,
                    "method": method,
                    "annual": m["annual"],
                    "vol": m["vol"],
                    "sharpe": m["sharpe"],
                    "maxdd": m["maxdd"],
                    "calmar": m["calmar"]
                })
                print(f"    {method:<16} | Ann: {m['annual']:+.2%} | Sharpe: {m['sharpe']:.2f} | MaxDD: {m['maxdd']:.2%} | Calmar: {m['calmar']:.2f}")
            except Exception as e:
                print(f"    {method:<16} | Failed: {str(e)}")

    # Summary table
    print("\n" + "=" * 85)
    print("  SUMMARY TABLE (Ranked by Sharpe)")
    print("=" * 85)
    res_df = pd.DataFrame(results).sort_values("sharpe", ascending=False)
    print(res_df.to_string(index=False, formatters={
        "annual": "{:+.2%}".format,
        "vol": "{:.2%}".format,
        "sharpe": "{:.2f}".format,
        "maxdd": "{:+.2%}".format,
        "calmar": "{:.2f}".format
    }))


if __name__ == "__main__":
    main()
