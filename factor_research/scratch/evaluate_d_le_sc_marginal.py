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

from portfolio.strategy_runners import run_active, _load_panels
from portfolio.marginal import evaluate
from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
import factors.d_le_sc
from strategies.d_le_sc import build_d_le_sc_weights
from lake.load_lake import load_prices, load_raw_close

def run_d_le_sc_returns(net_type, method, reb, direction, start_str="2018-01-01"):
    start_dt = pd.Timestamp(start_str)
    load_start_dt = start_dt - pd.Timedelta(days=120)
    load_start_str = load_start_dt.strftime("%Y-%m-%d")

    px = load_prices(start=load_start_str, fields=("open", "close", "volume", "amount"))
    raw_close = load_raw_close(start=load_start_str)

    close = px["close"]
    volume = px["volume"]
    amount = px["amount"]
    open_px = px["open"]

    common_idx = close.index
    if not raw_close.empty:
        raw_close = raw_close.reindex(index=common_idx, columns=close.columns)
    else:
        raw_close = close.copy()

    panels = {
        "open": open_px.reindex(index=common_idx, columns=close.columns),
        "close": close,
        "volume": volume,
        "amount": amount,
        "raw_close": raw_close,
    }

    # Compute factor
    factor, univ = factors.d_le_sc.build_d_le_sc_factor(
        panels,
        universe_size=800,
        lookback=60,
        network_type=net_type,
        correlation_method=method,
        rebalance_days=reb,
    )

    # Apply direction
    factor = direction * factor
    scheduled = build_d_le_sc_weights(factor, close, top_n=25)

    # Configure engine with standard costs
    prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_close)
    engine_config = BacktestConfig(
        start=start_str,
        cost=CostModel(
            buy_cost=0.00225,
            sell_cost=0.00275,
            financing_rate=0.0,
        ),
        leverage=1.0,
    )

    engine = BacktestEngine(prices=prices, config=engine_config)
    long_signal = Signal(weights=scheduled, timing=None)
    res_long = engine.run(long_signal)

    # Compute Universe Benchmark (Shifted 1 Day to avoid leak)
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()

    # Align dates
    common_idx = res_long.returns.index.intersection(bench_returns.index)
    r_long = res_long.returns.loc[common_idx]
    r_bench = bench_returns.loc[common_idx]

    # Hedged return (annual hedge cost 1.5%)
    daily_hedge_cost = 0.015 / 252.0
    r_neutral = r_long - r_bench - daily_hedge_cost

    return r_neutral.loc[start_dt:].dropna()

def main():
    print("=" * 75)
    print("Running Portfolio Marginal Contribution Evaluation for d-LE-SC v1.1...")
    print("=" * 75)

    # 1. Run active strategies
    print("\n[1/3] Running active live strategies (since 2018-01-01)...")
    existing_live = run_active(start="2018-01-01")
    for name, ret in existing_live.items():
        print(f"  Active strategy: {name} (length={len(ret)}, start={ret.index[0].date()}, end={ret.index[-1].date()})")

    # 2. Run candidate strategy
    print("\n[2/3] Running candidate strategy d-le-sc-hedged v1.1...")
    candidate_returns = run_d_le_sc_returns(
        net_type="preclose_lead_close",
        method="pearson",
        reb=20,
        direction=-1,
        start_str="2018-01-01"
    )
    print(f"  Candidate strategy returns: length={len(candidate_returns)}, start={candidate_returns.index[0].date()}, end={candidate_returns.index[-1].date()}")

    # 3. Generate market returns
    close, _, _ = _load_panels("2018-01-01")
    market_returns = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).mean(axis=1).fillna(0.0)

    # Align indices of all returns
    common_idx = candidate_returns.index
    for r in existing_live.values():
        common_idx = common_idx.intersection(r.index)
    common_idx = common_idx.intersection(market_returns.index)

    candidate_returns = candidate_returns.loc[common_idx]
    existing_live_aligned = {name: r.loc[common_idx] for name, r in existing_live.items()}
    market_returns = market_returns.loc[common_idx]

    # 4. Evaluate marginal contribution
    print("\n[3/3] Evaluating marginal contribution and defensive characteristics...")
    report = evaluate(candidate_returns, "d-le-sc-hedged.v1.1", existing_live_aligned, market_returns)

    print("\n" + "=" * 75)
    print("EVALUATION REPORT")
    print("=" * 75)
    print(f"Candidate Strategy: {report['candidate']}")
    print(f"Assigned Grade:     {report['grade']}")
    print(f"Recommendation:     {report['recommendation']}")
    print("-" * 75)
    print("Full Sample Performance Comparison:")
    print(f"  Baseline Sharpe:  {report['full_sample']['baseline_sharpe']:.3f}")
    print(f"  Combined Sharpe:  {report['full_sample']['combined_sharpe']:.3f}")
    print(f"  Delta Sharpe:    {report['full_sample']['delta_sharpe']:+.3f}")
    print(f"  Baseline Max DD:  {report['full_sample']['baseline_maxdd']:.2%}")
    print(f"  Combined Max DD:  {report['full_sample']['combined_maxdd']:.2%}")
    print(f"  Delta Max DD:    {report['full_sample']['delta_maxdd']:+.2%}")
    print("-" * 75)
    print("Regime Weighted Score Details:")
    print(f"  Regime Weighted Score: {report['regime_weighted_score']:.3f}")
    for regime, details in report['regime_details'].items():
        print(f"  - {regime:<15}: base_sh={details['base_sharpe']:.2f}, comb_sh={details['comb_sharpe']:.2f}, delta={details['delta']:+.2f}, weight={details['weight']:.2f}")
    print("-" * 75)
    print("Defensive Grade Analysis:")
    print(f"  Grade:            {report['defensive']['grade']}")
    print(f"  Bear Annual Ret:  {report['defensive']['bear_annual']:+.2%}")
    print(f"  Bear Ok:          {report['defensive']['bear_ok']}")
    print(f"  Corr Ok:          {report['defensive']['corr_ok']}")
    print(f"  Average Corr:     {report['correlation']['avg_corr']:.3f}")
    for name, corr in report['correlation']['per_live'].items():
        print(f"  - Corr to {name:<20}: {corr:+.3f}")
    print("=" * 75)

if __name__ == "__main__":
    main()
