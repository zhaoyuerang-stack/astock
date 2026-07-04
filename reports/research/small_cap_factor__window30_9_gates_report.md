# Research-to-Production Risk Report: small_cap_factor__window30_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=45.3%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ⚠️ WARN | WARN | Gate 1: Thesis verification complete. Mechanism length=63. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.1064, NW-ICIR=+0.1826, WinRate=76.3%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.5046, Retention=128.8% (Raw NW-ICIR=+0.3917) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.0552 (trials=1), PSR=100.0%, Skew=-0.54, Kurt=16.32 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=18.91%, MaxDD=-40.29%, Sharpe=0.89, Calmar=0.47 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=111.0%. Net Sharpe @ 5M=0.81, @ 50M=0.70, @ 500M=0.63 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.54 (win=100.0%). Delay 1d Sharpe=0.79. Bull Sharpe=4.36, Bear Sharpe=-4.68 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.54 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0750%, Expected Vol=1.3403%. Max Live Drawdown Limit=-60.4% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.4533,
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
  "thesis_len": 63,
  "citation_len": 26,
  "has_keywords": false
}
```

### Gate 2: Single Factor Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "ic_mean": 0.1064,
  "raw_icir": 0.6856,
  "nw_icir": 0.1826,
  "ic_win_rate": 0.7632,
  "ic_count": 3594,
  "quantile_returns": [
    -0.0018,
    0.0043,
    0.0097,
    0.0141,
    0.0193
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.040182385075073185,
    "5": 0.06728076627749792,
    "10": 0.08571919578644877,
    "20": 0.10657770112477498
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0799,
  "neut_raw_icir": 0.7984,
  "neut_nw_icir": 0.5046,
  "icir_retention": 1.2884
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.0552 after 1 trials

**Key Metrics:**
```json
{
  "skewness": -0.5438,
  "kurtosis": 16.3194,
  "n_periods": 3642,
  "dsr": 1.5967,
  "dsr_p_value": 0.0552,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9995,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Maximum drawdown exceeds threshold (20.0%): observed=-40.29%
- Sharpe ratio is below target (1.0): observed=0.89

**Key Metrics:**
```json
{
  "annual": 0.1891,
  "maxdd": -0.4029,
  "sharpe": 0.8887,
  "calmar": 0.4693,
  "turnover_annual": 33.5834,
  "cost_annual": 0.1145,
  "sortino": 0.683,
  "var_95": 0.0189,
  "cvar_95": 0.0349,
  "skew": -0.544,
  "kurtosis_excess": 13.3394,
  "tail_ratio": 1.107
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 111.0%

**Key Metrics:**
```json
{
  "annual_1x": 0.1891,
  "annual_2x": 0.0841,
  "annual_3x": -0.0208,
  "cost_decay_rate": 1.11,
  "capacity_curve": {
    "5000000": {
      "annual": 0.17340632111623633,
      "sharpe": 0.8138117985544178,
      "maxdd": -0.4071471370130251
    },
    "50000000": {
      "annual": 0.14969096397220596,
      "sharpe": 0.7003285180302785,
      "maxdd": -0.4133546011919317
    },
    "500000000": {
      "annual": 0.13598118574661291,
      "sharpe": 0.6334744557132248,
      "maxdd": -0.42692579298795297
    },
    "2000000000": {
      "annual": 0.134968742854592,
      "sharpe": 0.6280567499307731,
      "maxdd": -0.4328460360747939
    }
  },
  "capacity_limit_aum": 2000000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- Extreme regime dependency: Bear market return is severely negative: -85.62%

**Key Metrics:**
```json
{
  "wf_annual": 0.1111,
  "wf_sharpe": 0.5388,
  "wf_maxdd": -0.9238,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.1669,
  "sharpe_delay_1d": 0.7918,
  "annual_delay_2d": 0.1482,
  "sharpe_delay_2d": 0.7091,
  "bull_annual": 0.9601,
  "bull_sharpe": 4.3605,
  "bear_annual": -0.8562,
  "bear_sharpe": -4.6842
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
  "cv_sharpe": 0.5388,
  "cv_annual": 0.1111,
  "cv_maxdd": -0.9238,
  "cv_win_rate": 1.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0008,
  "daily_vol_expected": 0.0134,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0196,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.6044,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
