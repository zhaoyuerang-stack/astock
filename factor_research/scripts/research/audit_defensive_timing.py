#!/usr/bin/env python3
"""Defensive Timing Overlay Independent Parameter Audit.

Calculates the Deflated Sharpe Ratio (DSR) and parameter sensitivity
for the Small-Cap Moving Average trend overlay.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pandas as pd
from core.overlays.moving_average_overlay import MovingAverageOverlay
from strategies.small_cap import load_price_panels


def main() -> int:
    print("=" * 72)
    print("  Defensive Timing Overlay Independent Parameter Audit")
    print("=" * 72)

    # 1. Load data
    print("  [data] Loading stock price panels...")
    close, volume, amount = load_price_panels("2018-01-01")
    
    # Check if we have ETF data to estimate bond returns
    bond_returns = None
    etf_path = ROOT / "data_lake" / "cross_asset" / "etf" / "511010.parquet"
    if etf_path.exists():
        print("  [data] Loading 511010.parquet to calculate bond returns...")
        try:
            etf_df = pd.read_parquet(etf_path)
            etf_df["date"] = pd.to_datetime(etf_df["date"])
            etf_df = etf_df.set_index("date").sort_index()
            bond_returns = etf_df["close"].pct_change().fillna(0.0)
            print(f"    Loaded {len(bond_returns)} bond return periods.")
        except Exception as e:
            print(f"    Warning: Failed to load 511010.parquet ({e}), fallback to 0.0% cash yield.")
    else:
        print("    No ETF data found, fallback to 0.0% cash yield for BEAR regime.")

    # 2. Instantiate and run audit
    overlay = MovingAverageOverlay(ma_window=16)
    
    # Audit over window 5 to 60
    print("  [audit] Running parameter audit (MA window grid: 5 to 60)...")
    windows = list(range(5, 61))
    report = overlay.audit_parameters(close, amount, windows=windows, bond_returns=bond_returns)

    # 3. Print report
    print("-" * 72)
    print(f"  Chosen Window:      MA{report['chosen_window']}")
    print(f"  Chosen Sharpe:      {report['chosen_sharpe']:.4f}")
    print(f"  Best Window:        MA{report['best_window']}")
    print(f"  Best Sharpe:        {report['best_sharpe']:.4f}")
    print(f"  Number of Trials:   {report['n_trials']}")
    print(f"  Expected Max SR:    {report['expected_max_sr']:.4f}")
    print(f"  DSR p-value:        {report['dsr_p_value']:.6f}")
    
    status = "🟢 PASS (Significant)" if report["dsr_significant"] else "🔴 FAIL (Overfitted / Insignificant)"
    print(f"  DSR Verdict (alpha=0.05): {status}")
    print("-" * 72)

    # Print top 5 and bottom 5 parameter results
    sorted_res = sorted(report["results"], key=lambda x: x["sharpe_ratio"], reverse=True)
    print("  Top 5 parameter windows by Sharpe Ratio:")
    for r in sorted_res[:5]:
        print(f"    MA{r['window']:<2d}: Sharpe={r['sharpe_ratio']:.4f}, AnnRet={r['annual_return']:.2%}, MaxDD={r['max_drawdown']:.2%}")
    print("\n  Bottom 5 parameter windows by Sharpe Ratio:")
    for r in sorted_res[-5:]:
        print(f"    MA{r['window']:<2d}: Sharpe={r['sharpe_ratio']:.4f}, AnnRet={r['annual_return']:.2%}, MaxDD={r['max_drawdown']:.2%}")
    print("-" * 72)

    # 4. Save report to reports/research/
    reports_dir = ROOT / "reports" / "research"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    md_lines = [
        "# Defensive Timing Overlay Audit Report",
        "",
        f"Generated At: {pd.Timestamp.now()}",
        "",
        "## Core Parameters & Audit Results",
        "",
        f"- **Chosen Window**: MA{report['chosen_window']}",
        f"- **Chosen Sharpe Ratio**: {report['chosen_sharpe']:.4f}",
        f"- **Best Window**: MA{report['best_window']}",
        f"- **Best Sharpe Ratio**: {report['best_sharpe']:.4f}",
        f"- **Number of Trials**: {report['n_trials']} (tested windows: 5 to 60)",
        f"- **Expected Max Sharpe under Noise (E[max SR | H0])**: {report['expected_max_sr']:.4f}",
        f"- **DSR p-value**: {report['dsr_p_value']:.6f}",
        f"- **Statistical Significance (DSR < 0.05)**: {'YES (Significant)' if report['dsr_significant'] else 'NO (Insignificant)'}",
        "",
        "## Parameter Sensitivity Analysis",
        "",
        "| Window | Sharpe Ratio | Annualized Return | Max Drawdown |",
        "|---|---|---|---|",
    ]
    for r in report["results"]:
        md_lines.append(f"| MA{r['window']} | {r['sharpe_ratio']:.4f} | {r['annual_return']:.2%} | {r['max_drawdown']:.2%} |")

    report_file = reports_dir / "defensive_timing_audit.md"
    report_file.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"  [report] Written to: {report_file.relative_to(ROOT)}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
