# Research-to-Production Risk Report: illiquidity_clean-v1
**Run Date**: 2026-07-05 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=43.9%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=51. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0776, NW-ICIR=+0.1249, WinRate=70.3%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.4226, Retention=164.9% (Raw NW-ICIR=+0.2563) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.5773 (trials=7), PSR=99.0%, Skew=-0.96, Kurt=13.27 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=14.76%, MaxDD=-46.26%, Sharpe=0.63, Calmar=0.32 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=146.8%. Net Sharpe @ 5M=0.55, @ 50M=0.42, @ 500M=0.28 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.38 (win=91.7%). Delay 1d Sharpe=0.57. Bull Sharpe=4.10, Bear Sharpe=-4.57 |
| 7A | Purged + Embargoed CV | ❌ FAIL | FAIL | Gate 7A: CV Sharpe=0.38 (win=91.7%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0586%, Expected Vol=1.4781%. Max Live Drawdown Limit=-69.4% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.4385,
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
  "thesis_len": 51,
  "citation_len": 33,
  "has_keywords": true
}
```

### Gate 2: Single Factor Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "ic_mean": 0.0776,
  "raw_icir": 0.4649,
  "nw_icir": 0.1249,
  "ic_win_rate": 0.7035,
  "ic_count": 3602,
  "quantile_returns": [
    0.0003,
    0.0039,
    0.008,
    0.0138,
    0.0191
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.022887478645462322,
    "5": 0.04408971001117411,
    "10": 0.05993922617192888,
    "20": 0.07785751645514918
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0541,
  "neut_raw_icir": 0.7633,
  "neut_nw_icir": 0.4226,
  "icir_retention": 1.6486
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.5773 after 7 trials

**Key Metrics:**
```json
{
  "skewness": -0.9617,
  "kurtosis": 13.2657,
  "n_periods": 3642,
  "dsr": -0.195,
  "dsr_p_value": 0.5773,
  "e_max_sr": 0.7322,
  "dsr_significant": false,
  "psr": 0.9904,
  "n_trials": 7
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=14.76%
- Maximum drawdown exceeds threshold (20.0%): observed=-46.26%
- Sharpe ratio is below target (1.0): observed=0.63

**Key Metrics:**
```json
{
  "annual": 0.1476,
  "maxdd": -0.4626,
  "sharpe": 0.6292,
  "calmar": 0.3192,
  "turnover_annual": 34.6683,
  "cost_annual": 0.1179,
  "sortino": 0.4732,
  "var_95": 0.0222,
  "cvar_95": 0.0391,
  "skew": -0.9621,
  "kurtosis_excess": 10.2815,
  "tail_ratio": 1.0187
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 146.8%
- Capacity limit reached at 50.0M: Net Sharpe=0.42, Return=9.9%

**Key Metrics:**
```json
{
  "annual_1x": 0.1476,
  "annual_2x": 0.0393,
  "annual_3x": -0.069,
  "cost_decay_rate": 1.4676,
  "capacity_curve": {
    "5000000": {
      "annual": 0.12845078086316208,
      "sharpe": 0.5472650458388825,
      "maxdd": -0.5043840104604964
    },
    "50000000": {
      "annual": 0.09874357322082182,
      "sharpe": 0.4199865528464842,
      "maxdd": -0.5650343065397136
    },
    "500000000": {
      "annual": 0.06651000491554969,
      "sharpe": 0.281924010380638,
      "maxdd": -0.6344844411509074
    },
    "2000000000": {
      "annual": 0.0592469322734248,
      "sharpe": 0.2506564750657301,
      "maxdd": -0.6523880212578046
    }
  },
  "capacity_limit_aum": 50000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- OOS Walk-Forward aggregate Sharpe is weak (<0.50): observed=0.38
- Extreme regime dependency: Bear market return is severely negative: -96.34%

**Key Metrics:**
```json
{
  "wf_annual": 0.0824,
  "wf_sharpe": 0.3817,
  "wf_maxdd": -0.9788,
  "wf_positive_ratio": 0.9167,
  "annual_delay_1d": 0.1318,
  "sharpe_delay_1d": 0.5688,
  "annual_delay_2d": 0.1111,
  "sharpe_delay_2d": 0.4967,
  "bull_annual": 0.9755,
  "bull_sharpe": 4.0994,
  "bear_annual": -0.9634,
  "bear_sharpe": -4.5708
}
```

### Gate 7A: Purged + Embargoed CV (❌ FAIL)
**Reasons/Warnings:**
- Purged + Embargoed CV Sharpe is too weak: observed=0.38

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": 0.3817,
  "cv_annual": 0.0824,
  "cv_maxdd": -0.9788,
  "cv_win_rate": 0.9167
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0006,
  "daily_vol_expected": 0.0148,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0484,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.6939,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
