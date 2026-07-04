# Research-to-Production Risk Report: small_cap_factor__window45_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=47.4%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ⚠️ WARN | WARN | Gate 1: Thesis verification complete. Mechanism length=63. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0994, NW-ICIR=+0.1721, WinRate=75.3%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.4377, Retention=120.3% (Raw NW-ICIR=+0.3639) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.0509 (trials=1), PSR=100.0%, Skew=-0.59, Kurt=16.52 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=19.72%, MaxDD=-38.63%, Sharpe=0.92, Calmar=0.51 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=103.7%. Net Sharpe @ 5M=0.85, @ 50M=0.76, @ 500M=0.70 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.53 (win=100.0%). Delay 1d Sharpe=0.67. Bull Sharpe=4.46, Bear Sharpe=-4.63 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.53 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0782%, Expected Vol=1.3524%. Max Live Drawdown Limit=-57.9% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.474,
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
  "ic_mean": 0.0994,
  "raw_icir": 0.6443,
  "nw_icir": 0.1721,
  "ic_win_rate": 0.7527,
  "ic_count": 3579,
  "quantile_returns": [
    -0.001,
    0.0041,
    0.0093,
    0.0135,
    0.0186
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.03661787417977668,
    "5": 0.06179728646465442,
    "10": 0.07974717141979587,
    "20": 0.09987680335114482
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0722,
  "neut_raw_icir": 0.7251,
  "neut_nw_icir": 0.4377,
  "icir_retention": 1.2028
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.0509 after 1 trials

**Key Metrics:**
```json
{
  "skewness": -0.59,
  "kurtosis": 16.5178,
  "n_periods": 3642,
  "dsr": 1.6363,
  "dsr_p_value": 0.0509,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9997,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Maximum drawdown exceeds threshold (20.0%): observed=-38.63%
- Sharpe ratio is below target (1.0): observed=0.92

**Key Metrics:**
```json
{
  "annual": 0.1972,
  "maxdd": -0.3863,
  "sharpe": 0.9185,
  "calmar": 0.5105,
  "turnover_annual": 32.7199,
  "cost_annual": 0.1117,
  "sortino": 0.6994,
  "var_95": 0.0194,
  "cvar_95": 0.0352,
  "skew": -0.5902,
  "kurtosis_excess": 13.538,
  "tail_ratio": 1.0642
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 103.7%

**Key Metrics:**
```json
{
  "annual_1x": 0.1972,
  "annual_2x": 0.0949,
  "annual_3x": -0.0073,
  "cost_decay_rate": 1.0371,
  "capacity_curve": {
    "5000000": {
      "annual": 0.18350072776287185,
      "sharpe": 0.8547430454235001,
      "maxdd": -0.3898677276001238
    },
    "50000000": {
      "annual": 0.16270757214931442,
      "sharpe": 0.7572919927523207,
      "maxdd": -0.3953134251820969
    },
    "500000000": {
      "annual": 0.149954267058724,
      "sharpe": 0.6969549196232595,
      "maxdd": -0.4070810015991774
    },
    "2000000000": {
      "annual": 0.14893633274628587,
      "sharpe": 0.6917018658515012,
      "maxdd": -0.4133903578807552
    }
  },
  "capacity_limit_aum": 2000000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- Extreme regime dependency: Bear market return is severely negative: -86.65%

**Key Metrics:**
```json
{
  "wf_annual": 0.11,
  "wf_sharpe": 0.5341,
  "wf_maxdd": -0.9332,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.142,
  "sharpe_delay_1d": 0.6697,
  "annual_delay_2d": 0.125,
  "sharpe_delay_2d": 0.5953,
  "bull_annual": 0.9817,
  "bull_sharpe": 4.4583,
  "bear_annual": -0.8665,
  "bear_sharpe": -4.6272
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
  "cv_sharpe": 0.5341,
  "cv_annual": 0.11,
  "cv_maxdd": -0.9332,
  "cv_win_rate": 1.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0008,
  "daily_vol_expected": 0.0135,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0266,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.5794,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
