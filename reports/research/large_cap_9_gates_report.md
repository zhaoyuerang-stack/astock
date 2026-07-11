# Research-to-Production Risk Report: large_cap_v1.1-full
**Run Date**: 2026-07-05 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ❌ FAIL | FAIL | Gate 0: Data audit complete. NaN=96.3%, Infs=0, Outliers=237. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=50. |
| 2 | Single Factor Verification | ❌ FAIL | FAIL | Gate 2: Rank IC=-0.0083, NW-ICIR=+0.0151, WinRate=52.2%, MonoCorr=0.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.0390, Retention=128.9% (Raw NW-ICIR=+0.0302) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.7002 (trials=4), PSR=87.4%, Skew=-0.89, Kurt=16.75 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=6.36%, MaxDD=-47.73%, Sharpe=0.33, Calmar=0.13 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=62.8%. Net Sharpe @ 5M=0.27, @ 50M=0.21, @ 500M=0.15 |
| 7 | Out-of-Sample & Stress Testing | ❌ FAIL | FAIL | Gate 7: WF Sharpe=0.00 (win=0.0%). Delay 1d Sharpe=0.36. Bull Sharpe=1.97, Bear Sharpe=-1.67 |
| 7A | Purged + Embargoed CV | ❌ FAIL | FAIL | Gate 7A: CV Sharpe=0.00 (win=0.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0252%, Expected Vol=1.2223%. Max Live Drawdown Limit=-71.6% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (❌ FAIL)
**Reasons/Warnings:**
- Extremely high missing data: 96.3% of factor panel is NaN
- Found 237 extreme outliers (>10 std deviations)

**Key Metrics:**
```json
{
  "nan_pct": 0.9634,
  "inf_count": 0,
  "outliers_10std": 237,
  "lookahead_pert_diff": 0.0
}
```

### Gate 1: Economic Hypothesis (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "has_thesis": true,
  "thesis_len": 50,
  "citation_len": 23,
  "has_keywords": true
}
```

### Gate 2: Single Factor Verification (❌ FAIL)
**Reasons/Warnings:**
- NW-ICIR is below minimum threshold (0.03): observed=0.0151
- Weak monotonicity across 5 factor quantiles: Spearman corr=0.00

**Key Metrics:**
```json
{
  "ic_mean": -0.0083,
  "raw_icir": -0.0547,
  "nw_icir": 0.0151,
  "ic_win_rate": 0.5223,
  "ic_count": 2156,
  "quantile_returns": [
    0.0062,
    0.007,
    0.0066,
    0.0058,
    0.0068
  ],
  "monotonicity_corr": 0.0,
  "ic_decay": {
    "1": 0.0012519144326299052,
    "5": -0.006845073994369534,
    "10": -0.011759713918238369,
    "20": -0.010767215443370181
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0033,
  "neut_raw_icir": 0.0602,
  "neut_nw_icir": 0.039,
  "icir_retention": 1.2887
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.7002 after 4 trials
- Probabilistic Sharpe Ratio (Sharpe>0) is too low: PSR=87.4% (target >= 95.0%)

**Key Metrics:**
```json
{
  "skewness": -0.8943,
  "kurtosis": 16.7497,
  "n_periods": 3156,
  "dsr": -0.525,
  "dsr_p_value": 0.7002,
  "e_max_sr": 0.6539,
  "dsr_significant": false,
  "psr": 0.8744,
  "n_trials": 4
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=6.36%
- Maximum drawdown exceeds threshold (20.0%): observed=-47.73%
- Sharpe ratio is below target (1.0): observed=0.33

**Key Metrics:**
```json
{
  "annual": 0.0636,
  "maxdd": -0.4773,
  "sharpe": 0.3276,
  "calmar": 0.1332,
  "turnover_annual": 6.391,
  "cost_annual": 0.0272,
  "sortino": 0.2131,
  "var_95": 0.0176,
  "cvar_95": 0.0317,
  "skew": -0.8947,
  "kurtosis_excess": 13.7734,
  "tail_ratio": 1.1169
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 62.8%
- Capacity limit reached at 5.0M: Net Sharpe=0.27, Return=5.3%

**Key Metrics:**
```json
{
  "annual_1x": 0.0636,
  "annual_2x": 0.0436,
  "annual_3x": 0.0237,
  "cost_decay_rate": 0.6276,
  "capacity_curve": {
    "5000000": {
      "annual": 0.052715251411461966,
      "sharpe": 0.2715491433358828,
      "maxdd": -0.4918579540884429
    },
    "50000000": {
      "annual": 0.04043947308072913,
      "sharpe": 0.20801543694535868,
      "maxdd": -0.5098415694909963
    },
    "500000000": {
      "annual": 0.02902109625367225,
      "sharpe": 0.14897803006753474,
      "maxdd": -0.5300005086021606
    },
    "2000000000": {
      "annual": 0.026356536057027105,
      "sharpe": 0.1352269558410039,
      "maxdd": -0.5372511868235892
    }
  },
  "capacity_limit_aum": 5000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (❌ FAIL)
**Reasons/Warnings:**
- Walk-Forward validation failed to run due to lack of windows
- Extreme regime dependency: Bear market return is severely negative: -34.90%

**Key Metrics:**
```json
{
  "wf_annual": 0.0,
  "wf_sharpe": 0.0,
  "wf_maxdd": 0.0,
  "wf_positive_ratio": 0.0,
  "annual_delay_1d": 0.066,
  "sharpe_delay_1d": 0.3577,
  "annual_delay_2d": 0.0858,
  "sharpe_delay_2d": 0.4752,
  "bull_annual": 0.3555,
  "bull_sharpe": 1.9745,
  "bear_annual": -0.349,
  "bear_sharpe": -1.6654
}
```

### Gate 7A: Purged + Embargoed CV (❌ FAIL)
**Reasons/Warnings:**
- Walk-Forward CV failed: no windows generated

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": 0.0,
  "cv_annual": 0.0,
  "cv_maxdd": 0.0,
  "cv_win_rate": 0.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0003,
  "daily_vol_expected": 0.0122,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.1343,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.716,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
