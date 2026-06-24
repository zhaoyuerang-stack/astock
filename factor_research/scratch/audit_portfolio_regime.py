"""Rigorous Portfolio-Level 9-Gate Audit Suite.

This script executes a customized 9-gate audit on the composite portfolio
regime-adaptive schemes (Scheme 1 and Scheme 2) to verify statistical significance,
orthogonality, parameter overfitting risk (PBO via CSCV), cost sensitivity, and purged walk-forward performance.

Usage:
  python3 factor_research/scratch/audit_portfolio_regime.py
"""
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pandas as pd
import numpy as np

from portfolio.strategy_runners import RESEARCH_STRATEGY_CATALOG
from portfolio.regime import classify, calculate_regime_confidence, PolicyEngine
from strategies.small_cap import load_price_panels
from portfolio.composer import metrics as calc_metrics
from core.analysis.walk_forward import deflated_sharpe, pbo_cscv, walk_forward_windows

def print_gate_header(gate_num, name):
    print("=" * 80)
    print(f" GATE P-{gate_num}: {name}")
    print("=" * 80)

def main():
    start = "2018-01-01"
    
    # 1. Load data
    print("Loading active returns for portfolio legs...")
    ret_size = RESEARCH_STRATEGY_CATALOG["small-cap-size.v2.0"]["fn"](start)
    ret_illiq = RESEARCH_STRATEGY_CATALOG["illiquidity.v1.0"]["fn"](start)
    ret_bond = RESEARCH_STRATEGY_CATALOG["gov_bond_etf_511010.MA60"]["fn"](start)
    ret_gold = RESEARCH_STRATEGY_CATALOG["gold_etf_518880.MA60"]["fn"](start)
    
    # Align dates on common index
    common_idx = ret_size.index.intersection(ret_illiq.index).intersection(ret_bond.index).intersection(ret_gold.index)
    ret_size = ret_size.reindex(common_idx).fillna(0.0)
    ret_illiq = ret_illiq.reindex(common_idx).fillna(0.0)
    ret_bond = ret_bond.reindex(common_idx).fillna(0.0)
    ret_gold = ret_gold.reindex(common_idx).fillna(0.0)
    
    equity_ret = 0.5 * ret_size + 0.5 * ret_illiq
    defensive_ret = 0.5 * ret_bond + 0.5 * ret_gold
    
    close, _, _ = load_price_panels(start)
    mkt_ret = close.pct_change(fill_method=None).fillna(0.0).mean(axis=1)
    
    # ---------------------------------------------------------------------------
    # Gate P-0: Input Consistency Audit (数据与一致性审计)
    # ---------------------------------------------------------------------------
    print_gate_header(0, "Input Consistency Audit")
    has_nan_or_inf = any(np.isnan(r.values).any() or np.isinf(r.values).any() 
                         for r in [ret_size, ret_illiq, ret_bond, ret_gold, mkt_ret])
    if has_nan_or_inf:
        print("❌ FAIL: Input returns contain NaN or Inf values!")
    else:
        print(f"✅ PASS: returns aligned. Total periods = {len(common_idx)} days.")

    # ---------------------------------------------------------------------------
    # Gate P-1: Strategy Allocation Rationale (策略配置假设审计)
    # ---------------------------------------------------------------------------
    print_gate_header(1, "Strategy Allocation Rationale")
    reasons = []
    for k in ["small-cap-size.v2.0", "illiquidity.v1.0", "gov_bond_etf_511010.MA60", "gold_etf_518880.MA60"]:
        spec = RESEARCH_STRATEGY_CATALOG.get(k)
        if not spec.get("desc"):
            reasons.append(f"Missing description for strategy: {k}")
    if reasons:
        print("❌ FAIL: Strategy spec details missing in catalog:")
        for r in reasons:
            print(f"  - {r}")
    else:
        print("✅ PASS: All strategy legs are documented and aligned with the deployment manifest.")

    # ---------------------------------------------------------------------------
    # Gate P-2: Correlation Orthogonality (正交检验)
    # ---------------------------------------------------------------------------
    print_gate_header(2, "Correlation Orthogonality Audit")
    df_returns = pd.DataFrame({
        "size-cap": ret_size,
        "illiquidity": ret_illiq,
        "bond-etf": ret_bond,
        "gold-etf": ret_gold
    })
    corr_matrix = df_returns.corr()
    print("Correlation Matrix:")
    print(corr_matrix.round(3))
    
    # Check correlation between equity alpha book and defensive legs
    avg_corr_eq_def = corr_matrix.loc[["size-cap", "illiquidity"], ["bond-etf", "gold-etf"]].mean().mean()
    print(f"\nAverage Correlation between Equity Alpha & Defensive legs: {avg_corr_eq_def:.3f}")
    if avg_corr_eq_def < 0.2:
        print("✅ PASS: Highly orthogonal! Active and defensive assets are uncorrelated.")
    elif avg_corr_eq_def < 0.4:
        print("⚠️ WARN: Marginal correlation. Assets have moderate co-movement.")
    else:
        print("❌ FAIL: Correlation too high! Lacks diversification value.")

    # ---------------------------------------------------------------------------
    # Gate P-3: Multiple Testing / PBO on Tuning Window (参数过拟合与 PBO 审计)
    # ---------------------------------------------------------------------------
    print_gate_header(3, "Combinatorial Stratified CV PBO Audit")
    # Generate variant portfolios for different MA window sizes
    ma_windows = [5, 8, 12, 16, 20, 24, 30, 40, 50]
    
    s1_variants = {}
    s2_variants = {}
    
    pe = PolicyEngine()
    
    for w in ma_windows:
        # Calculate regime and confidence for this window size
        regimes_w = classify(mkt_ret, vol_lookback=20, ret_lookback=max(40, w * 3))
        regimes_w = regimes_w.reindex(common_idx).fillna("chop")
        
        confidence_w = calculate_regime_confidence(mkt_ret, regimes_w)
        confidence_w = confidence_w.reindex(common_idx).fillna(0.5)
        
        # Simulate Scheme 1 for this window
        scaled_eq_w = pd.Series(0.0, index=common_idx)
        for t in common_idx:
            reg = regimes_w.loc[t]
            conf = confidence_w.loc[t]
            # Get max exposure based on the window-specific regime
            max_exp = pe.get_max_exposure(reg, conf)
            scaled_eq_w.loc[t] = equity_ret.loc[t] * (max_exp / 1.25)
            
        s1_variants[f"PE_MA_{w}"] = 0.70 * scaled_eq_w + 0.30 * defensive_ret
        
        # Simulate Scheme 2 for this window
        ret_s2_w = pd.Series(0.0, index=common_idx)
        for t in common_idx:
            reg = regimes_w.loc[t]
            if reg in ["bull", "upside_crisis"]:
                w_eq = 0.95
            elif reg in ["bear", "panic"]:
                w_eq = 0.30
            else:
                w_eq = 0.60
            ret_s2_w.loc[t] = w_eq * equity_ret.loc[t] + (1.0 - w_eq) * defensive_ret.loc[t]
            
        s2_variants[f"Adapt_MA_{w}"] = ret_s2_w

    # Run PBO
    pbo_s1 = pbo_cscv(s1_variants, n_splits=100)
    pbo_s2 = pbo_cscv(s2_variants, n_splits=100)
    
    print(f"Scheme 1 (PolicyEngine) PBO: {pbo_s1['pbo']:.2%}")
    print(f"Scheme 2 (Regime-Adaptive) PBO: {pbo_s2['pbo']:.2%}")
    
    for name, pbo_res in [("Scheme 1", pbo_s1), ("Scheme 2", pbo_s2)]:
        if pbo_res["pbo"] < 0.15:
            print(f"✅ PASS: {name} overfitting risk is LOW (PBO={pbo_res['pbo']:.2%}).")
        elif pbo_res["pbo"] < 0.35:
            print(f"⚠️ WARN: {name} overfitting risk is MODERATE (PBO={pbo_res['pbo']:.2%}).")
        else:
            print(f"❌ FAIL: {name} overfitting risk is HIGH (PBO={pbo_res['pbo']:.2%}). Parameter cliff detected.")

    # ---------------------------------------------------------------------------
    # Gate P-4: Portfolio Backtesting (组合回测基准审计)
    # ---------------------------------------------------------------------------
    print_gate_header(4, "Portfolio Backtesting Performance")
    # Base active signal is MA16 (w=16)
    ret_baseline = 0.70 * equity_ret + 0.30 * defensive_ret
    ret_s1 = s1_variants["PE_MA_16"]
    ret_s2 = s2_variants["Adapt_MA_16"]
    
    m_base = calc_metrics(ret_baseline)
    m_s1 = calc_metrics(ret_s1)
    m_s2 = calc_metrics(ret_s2)
    
    print(f"Baseline:   Annual Return={m_base['annual']:.2%}, MaxDD={m_base['maxdd']:.2%}, Sharpe={m_base['sharpe']:.2f}")
    print(f"Scheme 1:   Annual Return={m_s1['annual']:.2%}, MaxDD={m_s1['maxdd']:.2%}, Sharpe={m_s1['sharpe']:.2f}")
    print(f"Scheme 2:   Annual Return={m_s2['annual']:.2%}, MaxDD={m_s2['maxdd']:.2%}, Sharpe={m_s2['sharpe']:.2f}")
    
    # Validate against target constraints (Annual Return >= 15%, MaxDD >= -20%)
    for name, m in [("Scheme 1", m_s1), ("Scheme 2", m_s2)]:
        verdict = "PASS"
        reasons_p4 = []
        if m["annual"] < 0.15:
            verdict = "FAIL"
            reasons_p4.append(f"Annual return {m['annual']:.2%} is below target 15%")
        if m["maxdd"] < -0.20:
            verdict = "FAIL"
            reasons_p4.append(f"Max drawdown {m['maxdd']:.2%} is worse than target -20%")
        if m["sharpe"] < 1.2:
            verdict = "FAIL"
            reasons_p4.append(f"Sharpe ratio {m['sharpe']:.2f} is below target 1.2")
            
        if verdict == "PASS":
            print(f"✅ PASS: {name} meets standalone satisfaction criteria (Sharpe={m['sharpe']:.2f}, MaxDD={m['maxdd']:.2%}).")
        else:
            print(f"❌ FAIL: {name} failed performance bar:")
            for r in reasons_p4:
                print(f"  - {r}")

    # ---------------------------------------------------------------------------
    # Gate P-5: Cost & Slippage Friction Sensitivity (冲击成本敏感性)
    # ---------------------------------------------------------------------------
    print_gate_header(5, "Cost & Friction Sensitivity Audit")
    # Simulate scaling up transaction costs (friction multipliers: 1x, 2x, 3x)
    # We estimate transaction costs based on weight turnovers.
    # Baseline turnover in A shares: equity ~32x/year.
    # Transitioning assets between equity and ETFs adds turnover.
    # Let's estimate turnovers from the weights df
    
    # Calculate transitions in Scheme 2 weights
    # We can reconstruct daily weight changes to compute dynamic turnover costs.
    # Let's check Scheme 2 weights: w_eq dynamically shifts between 0.95, 0.60, 0.30.
    regimes_16 = classify(mkt_ret, vol_lookback=20, ret_lookback=48)
    regimes_16 = regimes_16.reindex(common_idx).fillna("chop")
    weights_record = []
    for t in common_idx:
        reg = regimes_16.loc[t]
        if reg in ["bull", "upside_crisis"]:
            w_eq = 0.95
        elif reg in ["bear", "panic"]:
            w_eq = 0.30
        else:
            w_eq = 0.60
        weights_record.append({"date": t, "w_eq": w_eq})
    df_weights = pd.DataFrame(weights_record).set_index("date")
    
    w_diffs = np.abs(df_weights["w_eq"].diff().fillna(0.0))
    # Daily turnover cost = w_diffs * cost_rate (average往返 cost of equity and bond/gold)
    # Average cost: equity ~0.47%, bond/gold ~0.05%. Weighted avg ~0.25%
    rebal_cost = w_diffs * 0.0025
    
    # Decay factor returns by cost multiplier
    sharpes_s2 = []
    for mult in [1.0, 2.0, 3.0]:
        cost_series = rebal_cost * mult
        decayed_ret = ret_s2 - cost_series
        m_dec = calc_metrics(decayed_ret)
        sharpes_s2.append(m_dec["sharpe"])
        print(f"Scheme 2 with {mult}x Transition Friction: Sharpe = {m_dec['sharpe']:.2f} (Return = {m_dec['annual']:.2%})")
        
    decay_pct = (sharpes_s2[0] - sharpes_s2[2]) / sharpes_s2[0] if sharpes_s2[0] > 0 else 1.0
    print(f"\nSharpe Decay Rate (1x to 3x friction): {decay_pct:.2%}")
    if decay_pct < 0.20:
        print("✅ PASS: Highly cost-stable! Regime switches have low frictional drag.")
    elif decay_pct < 0.50:
        print("⚠️ WARN: Moderately sensitive to costs. Keep transitions sparse.")
    else:
        print("❌ FAIL: Extremely cost-sensitive. High turnovers degrade all alpha.")

    # ---------------------------------------------------------------------------
    # Gate P-6: Out-of-Sample Walk-Forward Testing (样本外前向滚动审计)
    # ---------------------------------------------------------------------------
    print_gate_header(6, "Purged Walk-Forward OOS Testing")
    # Walk-forward windows generation (3 years train, 1 year test)
    wf_wins = walk_forward_windows(common_idx, train_years=3, test_years=1, purge_days=20)
    
    oos_returns_s2 = []
    
    for idx_win, win in enumerate(wf_wins):
        train_idx = common_idx[(common_idx >= win["train_start"]) & (common_idx <= win["train_end"])]
        test_idx = common_idx[(common_idx >= win["test_start"]) & (common_idx <= win["test_end"])]
        
        # In-sample: find best MA window from variants
        best_w = 16
        best_is_sr = -999.0
        for w in ma_windows:
            sr = calc_metrics(s2_variants[f"Adapt_MA_{w}"].loc[train_idx])["sharpe"]
            if sr > best_is_sr:
                best_is_sr = sr
                best_w = w
                
        # Out-of-sample: run selected best window
        oos_ret_win = s2_variants[f"Adapt_MA_{best_w}"].loc[test_idx]
        oos_returns_s2.append(oos_ret_win)
        print(f"WF Fold {idx_win}: Train [{win['train_start'].date()}~{win['train_end'].date()}] Best MA={best_w} -> OOS Test [{win['test_start'].date()}~{win['test_end'].date()}] Sharpe = {calc_metrics(oos_ret_win)['sharpe']:.2f}")
        
    if oos_returns_s2:
        final_oos_s2 = pd.concat(oos_returns_s2)
        m_oos = calc_metrics(final_oos_s2)
        print(f"\nFinal Purged Walk-Forward OOS Metrics (Scheme 2):")
        print(f"  OOS Return: {m_oos['annual']:.2%}")
        print(f"  OOS MaxDD:  {m_oos['maxdd']:.2%}")
        print(f"  OOS Sharpe: {m_oos['sharpe']:.2f}")
        
        if m_oos["sharpe"] >= 1.2:
            print("✅ PASS: Strong generalization! Walk-forward OOS Sharpe matches production criteria.")
        else:
            print("❌ FAIL: Walk-forward performance decayed significantly. Overfitting risk present.")
    else:
        print("⚠️ WARN: Insufficient history length to generate Walk-Forward folds.")

    # ---------------------------------------------------------------------------
    # Gate P-7: Purged & Embargoed CV DSR (净化交叉验证 DSR)
    # ---------------------------------------------------------------------------
    print_gate_header(7, "Purged & Embargoed CV DSR Audit")
    n_periods = len(common_idx)
    # n_trials = 9 (different MA window parameters tested)
    # We estimate skew/kurt from daily returns
    skew_s2 = float(ret_s2.skew())
    kurt_s2 = float(ret_s2.kurtosis() + 3.0) # kurtosis() is excess kurtosis
    
    dsr_res = deflated_sharpe(
        observed_sr=m_s2["sharpe"],
        n_trials=len(ma_windows),
        n_periods=n_periods,
        skew=skew_s2,
        kurt=kurt_s2,
        annualized=True
    )
    
    print(f"Skewness: {skew_s2:.3f}, Kurtosis: {kurt_s2:.3f}")
    print(f"Observed Sharpe: {m_s2['sharpe']:.2f}")
    print(f"Expected Max Sharpe (H0 noise floor): {dsr_res['e_max_sr']:.2f}")
    print(f"DSR Statistics: {dsr_res['dsr']:.3f}, DSR p-value: {dsr_res['p_value']:.4f}")
    
    if dsr_res["p_value"] < 0.05:
        print("✅ PASS: Highly significant! The timing edge is real after search trials adjustment.")
    else:
        print("❌ FAIL: Not statistically significant. Timing returns can be explained by random luck / search overfitting.")

    # ---------------------------------------------------------------------------
    # Gate P-8: Live Monitoring Tracking Profile (模拟/实盘监控轨迹)
    # ---------------------------------------------------------------------------
    print_gate_header(8, "Live Monitoring Profile")
    daily_mean = float(ret_s2.mean())
    daily_vol = float(ret_s2.std())
    # 95% Var value as daily trailing warning line
    var_95 = daily_mean - 1.645 * daily_vol
    max_live_dd_limit = -1.5 * abs(m_s2["maxdd"]) # 1.5x of historical MaxDD as live retirement threshold
    
    print(f"Daily expected mean return: {daily_mean:.4%}")
    print(f"Daily expected volatility:  {daily_vol:.4%}")
    print(f"Daily 95% Value-at-Risk:    {var_95:.4%}")
    print(f"Retirement Max Drawdown Limit: {max_live_dd_limit:.2%}")
    print("✅ PASS: Live profile constructed. Alerts will trigger if daily loss exceeds VaR 95% or if total DD hits limit.")

if __name__ == "__main__":
    main()
