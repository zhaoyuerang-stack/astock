"""Portfolio composition CLI.

Usage:
  python3 apps/portfolio_cli.py --compose equal_weight
  python3 apps/portfolio_cli.py --compose risk_parity
  python3 apps/portfolio_cli.py --compose regime_adaptive
  python3 apps/portfolio_cli.py --analyze
"""
import argparse, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel
from strategies.small_cap import load_price_panels
from factors.utils import safe_zscore, mad_clip
from factors.small_cap import small_cap_timing
from strategies.size_earnings import build_vol_target
from lake.load_lake import load_fundamental_panel

from portfolio.composer import compose, metrics as port_metrics
from portfolio.analysis import (
    correlation_matrix, contribution_decompose, regime_breakdown, rolling_correlation,
)


# ═══════════════════════════════════════════════════
# Strategy builders
# ═══════════════════════════════════════════════════

class Illiq:
    def __init__(self, w=20): self.w = w
    def __call__(self, c, v, a, d):
        r = c.pct_change(fill_method=None).abs().replace([np.inf, -np.inf], np.nan)
        return safe_zscore(mad_clip((r/(a+1)).rolling(self.w).mean()))

class SizeLoVol:
    def __init__(self, vw=20): self.vw = vw
    def __call__(self, c, v, a, d):
        sz = -np.log(a.rolling(60).mean()+1)
        r = c.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
        return safe_zscore(mad_clip(sz - r.rolling(self.vw).std()))


def run_strategy(name, factor, timing, leverage=1.25):
    """Run a single strategy and return daily returns."""
    close, volume, amount = load_price_panels("2010-01-01")
    td = close.index

    if callable(factor):
        factor = factor(close, volume, amount, td)
    if callable(timing):
        timing = timing(close, amount)

    def wts(f, c, n=25, reb=20):
        fd = f.dropna(how="all").index.intersection(c.index)
        if len(fd) < 50: return {}
        w = {}
        for rd in list(fd[::reb]):
            pos = c.index.get_loc(rd)
            if pos+1 >= len(c.index): continue
            eff = c.index[pos+1]
            fv = f.loc[rd].dropna()
            act = c.loc[rd].dropna().index
            fv = fv.reindex(act).dropna()
            if len(fv) < n: continue
            w[eff] = pd.Series(1.0/n, index=fv.nlargest(n).index)
        return w

    w = wts(factor, close)
    prices = PricePanel(close=close, volume=volume, amount=amount)
    cfg = BacktestConfig(start="2018-01-01", leverage=leverage)
    r = BacktestEngine(prices=prices, config=cfg).run(
        Signal(weights=w, timing=timing, family=name, version="v1.0"))
    return r.returns, close.index


def load_all_strategies():
    """Run all 4 strategies, return dict of daily returns."""
    print("Loading strategies (this takes ~2 min)...", flush=True)

    # Shared timing
    close, volume, amount = load_price_panels("2010-01-01")
    td = close.index
    pt, _, _ = small_cap_timing(close, amount, 16)
    pt_f = pt.astype(float)

    # illiquidity
    print("  [1/4] illiquidity...", flush=True)
    il_f = Illiq(20)(close, volume, amount, td)
    ret_il, _ = run_strategy("illiquidity", il_f, pt_f, 1.25)

    # size-low-vol
    print("  [2/4] size-low-vol...", flush=True)
    slv_f = SizeLoVol(20)(close, volume, amount, td)
    ret_slv, _ = run_strategy("size-low-vol", slv_f, pt_f, 1.25)

    # size-earnings
    print("  [3/4] size-earnings...", flush=True)
    fund = load_fundamental_panel(td, fields=['net_profit_yoy'])
    npy = fund.get('net_profit_yoy', pd.DataFrame()).reindex(td).ffill()
    se_f = safe_zscore(mad_clip(0.5*safe_zscore(mad_clip(-np.log(amount.rolling(60).mean()+1))) + 0.5*safe_zscore(mad_clip(npy))))
    vt = build_vol_target(close, amount, target_vol=0.25, lookback=60)
    ret_se, _ = run_strategy("size-earnings", se_f, pt_f * vt, 1.10)

    # illiq+size blend
    print("  [4/4] illiq+size...", flush=True)
    isz_f = safe_zscore(mad_clip(il_f + safe_zscore(mad_clip(-np.log(amount.rolling(60).mean()+1)))))
    ret_isz, _ = run_strategy("illiq+size", isz_f, pt_f, 1.25)

    print("  Done.", flush=True)

    return {
        "illiquidity": ret_il,
        "size-low-vol": ret_slv,
        "size-earnings": ret_se,
        "illiq+size": ret_isz,
    }, pt_f


# ═══════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════

def cmd_compose(returns, regime, method):
    """Compose portfolio and print results."""
    port_ret, weights = compose(returns, method=method, regime_signal=regime)
    m = port_metrics(port_ret)

    print(f"\n{'='*60}")
    print(f"  Portfolio: {method.upper()}")
    print(f"{'='*60}")
    print(f"  Annual: {m['annual']:+.1%}  MaxDD: {m['maxdd']:+.1%}  "
          f"Sharpe: {m['sharpe']:.2f}  Calmar: {m['calmar']:.2f}  "
          f"Days: {m['n_days']}")

    # Compare to individual strategies
    print(f"\n  vs Individual Strategies:")
    print(f"  {'Strategy':<20} {'Annual':>8} {'MaxDD':>8} {'Sharpe':>7}")
    print(f"  {'-'*45}")
    for name in returns:
        m_s = port_metrics(returns[name])
        print(f"  {name:<20} {m_s['annual']:>+7.1%} {m_s['maxdd']:>+7.1%} {m_s['sharpe']:>+6.2f}")
    print(f"  {'-'*45}")
    print(f"  {'PORTFOLIO':<20} {m['annual']:>+7.1%} {m['maxdd']:>+7.1%} {m['sharpe']:>+6.2f}")


def cmd_analyze(returns, regime):
    """Run full analysis suite."""
    print(f"\n{'='*60}")
    print(f"  PORTFOLIO ANALYSIS")
    print(f"{'='*60}")

    # Correlation matrix
    corr = correlation_matrix(returns)
    print(f"\n  Correlation Matrix:")
    print(corr.round(3).to_string())

    # Contribution decomposition (equal weight baseline)
    contrib = contribution_decompose(returns)
    print(f"\n  Contribution Decomposition (equal weight):")
    print(f"  {'Strategy':<20} {'Weight':>7} {'Ann':>7} {'Contrib':>8} {'Risk%':>7} {'MargS':>7}")
    for idx, row in contrib.iterrows():
        print(f"  {idx:<20} {row['weight']:>6.1%} {row['annual']:>+6.1%} "
              f"{row['ann_contrib_pct']:>7.1%} {row['risk_contrib_pct']:>6.1%} "
              f"{row['marginal_sharpe']:>+6.2f}")

    # Regime breakdown
    if regime is not None:
        rb = regime_breakdown(returns, regime)
        print(f"\n  Regime Breakdown (PureTrend ON vs OFF):")
        print(rb.round(3).to_string())

    # Rolling correlation
    names = list(returns.keys())
    if len(names) >= 2:
        a, b = names[0], names[1]
        rc = rolling_correlation(returns, 252)
        print(f"\n  Rolling 252d Correlation ({a} vs {b}):")
        print(f"    Mean: {rc.mean():.3f}  Min: {rc.min():.3f}  Max: {rc.max():.3f}  "
              f"<0.5: {(rc<0.5).mean():.0%}")


# ═══════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compose", choices=["equal_weight", "risk_parity", "regime_adaptive"],
                    help="Run portfolio composition")
    ap.add_argument("--analyze", action="store_true", help="Run full analysis")
    args = ap.parse_args()

    if not args.compose and not args.analyze:
        ap.print_help()
        return

    returns, regime = load_all_strategies()

    if args.compose:
        cmd_compose(returns, regime, args.compose)

    if args.analyze:
        cmd_analyze(returns, regime)


if __name__ == "__main__":
    main()
