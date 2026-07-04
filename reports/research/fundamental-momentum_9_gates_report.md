# Research-to-Production Risk Report: fundamental-momentum_v0.1
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=0.0%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=52. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0658, NW-ICIR=+0.1489, WinRate=72.9%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.3666, Retention=116.6% (Raw NW-ICIR=+0.3145) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.2973 (trials=1), PSR=97.4%, Skew=+1.51, Kurt=46.12 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=14.41%, MaxDD=-49.62%, Sharpe=0.50, Calmar=0.29 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=153.6%. Net Sharpe @ 5M=0.46, @ 50M=0.39, @ 500M=0.27 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.36 (win=91.7%). Delay 1d Sharpe=0.46. Bull Sharpe=3.76, Bear Sharpe=-4.01 |
| 7A | Purged + Embargoed CV | ❌ FAIL | FAIL | Gate 7A: CV Sharpe=0.36 (win=91.7%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0572%, Expected Vol=1.8049%. Max Live Drawdown Limit=-74.4% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.0,
  "inf_count": 0,
  "outliers_10std": 0,
  "lookahead_pert_diff": 0.0
}
```

### Gate 1: Economic Hypothesis (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "has_thesis": true,
  "thesis_len": 52,
  "citation_len": 42,
  "has_keywords": true
}
```

### Gate 2: Single Factor Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "ic_mean": 0.0658,
  "raw_icir": 0.5305,
  "nw_icir": 0.1489,
  "ic_win_rate": 0.7286,
  "ic_count": 3563,
  "quantile_returns": [
    0.0027,
    0.0095,
    0.012,
    0.0123,
    0.014
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.02849344520080216,
    "5": 0.046581361936029485,
    "10": 0.0550036521044004,
    "20": 0.06509541635948622
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0478,
  "neut_raw_icir": 0.6048,
  "neut_nw_icir": 0.3666,
  "icir_retention": 1.1657
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.2973 after 1 trials

**Key Metrics:**
```json
{
  "skewness": 1.5076,
  "kurtosis": 46.1248,
  "n_periods": 3642,
  "dsr": 0.5321,
  "dsr_p_value": 0.2973,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9743,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=14.41%
- Maximum drawdown exceeds threshold (20.0%): observed=-49.62%
- Sharpe ratio is below target (1.0): observed=0.50

**Key Metrics:**
```json
{
  "annual": 0.1441,
  "maxdd": -0.4962,
  "sharpe": 0.5031,
  "calmar": 0.2905,
  "turnover_annual": 35.4212,
  "cost_annual": 0.1203,
  "sortino": 0.414,
  "var_95": 0.0262,
  "cvar_95": 0.0445,
  "skew": 1.5082,
  "kurtosis_excess": 43.1857,
  "tail_ratio": 1.0306
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 153.6%
- Capacity limit reached at 5.0M: Net Sharpe=0.46, Return=13.3%

**Key Metrics:**
```json
{
  "annual_1x": 0.1441,
  "annual_2x": 0.0334,
  "annual_3x": -0.0773,
  "cost_decay_rate": 1.536,
  "capacity_curve": {
    "5000000": {
      "annual": 0.13281307586217583,
      "sharpe": 0.4636519065338901,
      "maxdd": -0.5186555692206545
    },
    "50000000": {
      "annual": 0.11273971215059804,
      "sharpe": 0.39360309460019016,
      "maxdd": -0.5564362407253108
    },
    "500000000": {
      "annual": 0.07630750173925427,
      "sharpe": 0.2661381229037317,
      "maxdd": -0.6180447466436059
    },
    "2000000000": {
      "annual": 0.06147519552023083,
      "sharpe": 0.214213607056349,
      "maxdd": -0.6503380351332492
    }
  },
  "capacity_limit_aum": 5000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- OOS Walk-Forward aggregate Sharpe is weak (<0.50): observed=0.36
- Extreme regime dependency: Bear market return is severely negative: -109.82%

**Key Metrics:**
```json
{
  "wf_annual": 0.087,
  "wf_sharpe": 0.3647,
  "wf_maxdd": -0.9731,
  "wf_positive_ratio": 0.9167,
  "annual_delay_1d": 0.1229,
  "sharpe_delay_1d": 0.4623,
  "annual_delay_2d": 0.0806,
  "sharpe_delay_2d": 0.3198,
  "bull_annual": 1.0605,
  "bull_sharpe": 3.7641,
  "bear_annual": -1.0982,
  "bear_sharpe": -4.0055
}
```

### Gate 7A: Purged + Embargoed CV (❌ FAIL)
**Reasons/Warnings:**
- Purged + Embargoed CV Sharpe is too weak: observed=0.36

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": 0.3647,
  "cv_annual": 0.087,
  "cv_maxdd": -0.9731,
  "cv_win_rate": 0.9167
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0006,
  "daily_vol_expected": 0.018,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0601,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.7443,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
