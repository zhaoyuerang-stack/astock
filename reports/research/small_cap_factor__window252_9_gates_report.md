# Research-to-Production Risk Report: small_cap_factor__window252_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ⚠️ WARN | WARN | Gate 0: Data audit complete. NaN=63.1%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ⚠️ WARN | WARN | Gate 1: Thesis verification complete. Mechanism length=64. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0677, NW-ICIR=+0.1109, WinRate=66.8%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.1938, Retention=89.5% (Raw NW-ICIR=+0.2166) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.1284 (trials=1), PSR=99.5%, Skew=-1.03, Kurt=19.02 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=15.17%, MaxDD=-41.77%, Sharpe=0.70, Calmar=0.36 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=100.2%. Net Sharpe @ 5M=0.68, @ 50M=0.65, @ 500M=0.62 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.45 (win=100.0%). Delay 1d Sharpe=0.76. Bull Sharpe=3.72, Bear Sharpe=-4.01 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.45 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0602%, Expected Vol=1.3617%. Max Live Drawdown Limit=-62.7% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (⚠️ WARN)
**Reasons/Warnings:**
- High missing data: 63.1% of factor panel is NaN

**Key Metrics:**
```json
{
  "nan_pct": 0.6312,
  "inf_count": 0,
  "outliers_10std": 0,
  "lookahead_pert_diff": 0.0
}
```

### Gate 1: Economic Hypothesis (⚠️ WARN)
**Reasons/Warnings:**
- Mechanism lacks standard financial/behavioral economic terms (e.g. risk premium, behavioral bias, etc.)

**Key Metrics:**
```json
{
  "has_thesis": true,
  "thesis_len": 64,
  "citation_len": 27,
  "has_keywords": false
}
```

### Gate 2: Single Factor Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "ic_mean": 0.0677,
  "raw_icir": 0.4081,
  "nw_icir": 0.1109,
  "ic_win_rate": 0.6682,
  "ic_count": 3032,
  "quantile_returns": [
    0.0065,
    0.009,
    0.0133,
    0.0158,
    0.0194
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.025284000922990657,
    "5": 0.03967753397040089,
    "10": 0.051625181771023584,
    "20": 0.06606685160771168
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0298,
  "neut_raw_icir": 0.3901,
  "neut_nw_icir": 0.1938,
  "icir_retention": 0.8948
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.1284 after 1 trials

**Key Metrics:**
```json
{
  "skewness": -1.0294,
  "kurtosis": 19.0243,
  "n_periods": 3642,
  "dsr": 1.1341,
  "dsr_p_value": 0.1284,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9953,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Maximum drawdown exceeds threshold (20.0%): observed=-41.77%
- Sharpe ratio is below target (1.0): observed=0.70

**Key Metrics:**
```json
{
  "annual": 0.1517,
  "maxdd": -0.4177,
  "sharpe": 0.7019,
  "calmar": 0.3632,
  "turnover_annual": 24.3337,
  "cost_annual": 0.0843,
  "sortino": 0.4929,
  "var_95": 0.0184,
  "cvar_95": 0.0354,
  "skew": -1.0298,
  "kurtosis_excess": 16.0479,
  "tail_ratio": 1.0883
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 100.2%

**Key Metrics:**
```json
{
  "annual_1x": 0.1517,
  "annual_2x": 0.0757,
  "annual_3x": -0.0004,
  "cost_decay_rate": 1.0024,
  "capacity_curve": {
    "5000000": {
      "annual": 0.1473200831770947,
      "sharpe": 0.6814576999923184,
      "maxdd": -0.4190962695373781
    },
    "50000000": {
      "annual": 0.14032589525025335,
      "sharpe": 0.648959191573611,
      "maxdd": -0.42125637431675655
    },
    "500000000": {
      "annual": 0.13408740098522057,
      "sharpe": 0.6200054196790354,
      "maxdd": -0.4260348169486543
    },
    "2000000000": {
      "annual": 0.1332272676136173,
      "sharpe": 0.6160139155649567,
      "maxdd": -0.43016601328870263
    }
  },
  "capacity_limit_aum": 2000000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- OOS Walk-Forward aggregate Sharpe is weak (<0.50): observed=0.45
- Extreme regime dependency: Bear market return is severely negative: -76.80%

**Key Metrics:**
```json
{
  "wf_annual": 0.0946,
  "wf_sharpe": 0.4515,
  "wf_maxdd": -0.9509,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.1586,
  "sharpe_delay_1d": 0.7646,
  "annual_delay_2d": 0.1577,
  "sharpe_delay_2d": 0.7626,
  "bull_annual": 0.8301,
  "bull_sharpe": 3.7155,
  "bear_annual": -0.768,
  "bear_sharpe": -4.0146
}
```

### Gate 7A: Purged + Embargoed CV (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": 0.4515,
  "cv_annual": 0.0946,
  "cv_maxdd": -0.9509,
  "cv_win_rate": 1.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0006,
  "daily_vol_expected": 0.0136,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0583,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.6266,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
