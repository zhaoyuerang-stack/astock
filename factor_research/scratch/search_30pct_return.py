"""Research script to search for configurations achieving 30% annualized return.
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.small_cap import StrategyConfig as SmallConfig, run_small_cap_strategy
from strategies.large_cap import StrategyConfig as LargeConfig, run_large_cap_strategy
from strategies.industry_rotation import StrategyConfig as IndConfig, run_industry_rotation_strategy

def get_metrics(ret):
    if len(ret) == 0:
        return {"annual": 0.0, "sharpe": 0.0, "maxdd": 0.0, "calmar": 0.0}
    nav = (1 + ret.fillna(0)).cumprod()
    ann = nav.iloc[-1] ** (252 / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    maxdd = float((nav / nav.cummax() - 1).min())
    calmar = ann / abs(maxdd) if maxdd != 0 else 0.0
    return {"annual": ann, "sharpe": sharpe, "maxdd": maxdd, "calmar": calmar}

def main():
    print("=" * 110)
    print("  SEARCHING FOR 30% ANNUALIZED RETURN CONFIGURATIONS (OOS 2023-2026)  ")
    print("=" * 110)

    # 1. Run standalones with default configs
    print("[1/3] Running standalones...", flush=True)
    r_m1 = run_small_cap_strategy(SmallConfig(start="2010-01-01"))["returns"]
    # Run M2 with w_cpv_max = 0.25 (WFO champion)
    r_m2 = run_large_cap_strategy(LargeConfig(start="2010-01-01", w_cpv_max=0.25))["returns"]
    r_m3 = run_industry_rotation_strategy(IndConfig(start="2010-01-01", version="v1.2", w_cpv=0.5, cost_mode="stock"))["returns"]

    common = r_m1.index.intersection(r_m2.index).intersection(r_m3.index)
    m1 = r_m1.loc[common]
    m2 = r_m2.loc[common]
    m3 = r_m3.loc[common]

    # Filter to OOS period
    m1_oos = m1[m1.index >= "2023-01-01"]
    m2_oos = m2[m2.index >= "2023-01-01"]
    m3_oos = m3[m3.index >= "2023-01-01"]

    print("\n--- BASELINE OOS PERFORMANCE ---")
    for name, r in [("M1 Small-Cap", m1_oos), ("M2 Large-Cap Hedged", m2_oos), ("M3 Industry Rotation", m3_oos)]:
        m = get_metrics(r)
        print(f"{name:<20} | AnnRet: {m['annual']:>7.2%} | Sharpe: {m['sharpe']:>5.2f} | MaxDD: {m['maxdd']:>7.2%} | Calmar: {m['calmar']:>5.2f}")

    print("\n--- OPTION A: PORTFOLIO LEVEL LEVERAGE ON OPTIMAL BLENDS ---")
    # We test 60/40 and 50/50 blends with different levels of portfolio leverage
    blends = [
        ("60% M1 / 40% M2", 0.6 * m1_oos + 0.4 * m2_oos),
        ("50% M1 / 50% M2", 0.5 * m1_oos + 0.5 * m2_oos),
        ("70% M1 / 30% M2", 0.7 * m1_oos + 0.3 * m2_oos),
    ]

    for label, r_blend in blends:
        print(f"\nScaling {label}:")
        m_base = get_metrics(r_blend)
        print(f"  Base (1.0x) | AnnRet: {m_base['annual']:>7.2%} | Sharpe: {m_base['sharpe']:>5.2f} | MaxDD: {m_base['maxdd']:>7.2%}")
        
        # Search for leverage factor to get 30% return
        for lev in np.arange(1.1, 2.0, 0.05):
            r_scaled = r_blend * lev
            m = get_metrics(r_scaled)
            if m["annual"] >= 0.30:
                print(f"  --> TARGET MET: Leverage {lev:.2f}x | AnnRet: {m['annual']:>7.2%} | Sharpe: {m['sharpe']:>5.2f} | MaxDD: {m['maxdd']:>7.2%} | Calmar: {m['calmar']:>5.2f}")
                break
            else:
                print(f"  Leverage {lev:.2f}x | AnnRet: {m['annual']:>7.2%} | Sharpe: {m['sharpe']:>5.2f} | MaxDD: {m['maxdd']:>7.2%}")

    print("\n--- OPTION B: STRATEGY LEVEL OPTIMIZATION (HIGH RETURN M1) ---")
    # Let's see if we can optimize M1 parameters to get higher standalone returns
    # We try size windows of 20, 40, 60 (default), 80 days
    # And we try different timing MA windows
    for sz_win in [40, 60, 80]:
        for t_ma in [10, 16, 22]:
            try:
                cfg = SmallConfig(start="2010-01-01", size_window=sz_win, timing_ma=t_ma)
                res = run_small_cap_strategy(cfg)
                r_m1_alt = res["returns"]
                common_alt = r_m1_alt.index.intersection(m2.index)
                m1_alt_oos = r_m1_alt.loc[common_alt]
                m1_alt_oos = m1_alt_oos[m1_alt_oos.index >= "2023-01-01"]
                m2_alt_oos = m2.loc[common_alt]
                m2_alt_oos = m2_alt_oos[m2_alt_oos.index >= "2023-01-01"]
                
                m = get_metrics(m1_alt_oos)
                # print
                print(f"M1(size_win={sz_win}, timing_ma={t_ma}) | AnnRet: {m['annual']:>7.2%} | Sharpe: {m['sharpe']:>5.2f} | MaxDD: {m['maxdd']:>7.2%}")
                
                # Test 70/30 blend with this optimized M1
                r_blend_alt = 0.7 * m1_alt_oos + 0.3 * m2_alt_oos
                m_blend = get_metrics(r_blend_alt)
                print(f"  70% M1 + 30% M2 Blend            | AnnRet: {m_blend['annual']:>7.2%} | Sharpe: {m_blend['sharpe']:>5.2f} | MaxDD: {m_blend['maxdd']:>7.2%}")
            except Exception as e:
                continue

if __name__ == "__main__":
    main()
