# Research-to-Production Risk Report: small_cap_factor__window60_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=49.3%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ⚠️ WARN | WARN | Gate 1: Thesis verification complete. Mechanism length=63. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0919, NW-ICIR=+0.1577, WinRate=74.1%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.4067, Retention=124.1% (Raw NW-ICIR=+0.3276) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.0784 (trials=1), PSR=99.9%, Skew=-0.70, Kurt=16.58 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=17.33%, MaxDD=-41.25%, Sharpe=0.80, Calmar=0.42 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=113.3%. Net Sharpe @ 5M=0.75, @ 50M=0.66, @ 500M=0.61 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.55 (win=100.0%). Delay 1d Sharpe=0.66. Bull Sharpe=4.19, Bear Sharpe=-4.53 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.55 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0688%, Expected Vol=1.3605%. Max Live Drawdown Limit=-61.9% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.4925,
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
  "ic_mean": 0.0919,
  "raw_icir": 0.5925,
  "nw_icir": 0.1577,
  "ic_win_rate": 0.741,
  "ic_count": 3564,
  "quantile_returns": [
    -0.0001,
    0.0037,
    0.0088,
    0.0129,
    0.0179
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.0329018099751635,
    "5": 0.056834052901993476,
    "10": 0.07382913829219877,
    "20": 0.09234645155986329
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0666,
  "neut_raw_icir": 0.6808,
  "neut_nw_icir": 0.4067,
  "icir_retention": 1.2414
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.0784 after 1 trials

**Key Metrics:**
```json
{
  "skewness": -0.6975,
  "kurtosis": 16.5775,
  "n_periods": 3642,
  "dsr": 1.4162,
  "dsr_p_value": 0.0784,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9986,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Maximum drawdown exceeds threshold (20.0%): observed=-41.25%
- Sharpe ratio is below target (1.0): observed=0.80

**Key Metrics:**
```json
{
  "annual": 0.1733,
  "maxdd": -0.4125,
  "sharpe": 0.8022,
  "calmar": 0.42,
  "turnover_annual": 31.4135,
  "cost_annual": 0.1076,
  "sortino": 0.6079,
  "var_95": 0.0191,
  "cvar_95": 0.0356,
  "skew": -0.6978,
  "kurtosis_excess": 13.5979,
  "tail_ratio": 1.0698
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 113.3%

**Key Metrics:**
```json
{
  "annual_1x": 0.1733,
  "annual_2x": 0.0751,
  "annual_3x": -0.0231,
  "cost_decay_rate": 1.1332,
  "capacity_curve": {
    "5000000": {
      "annual": 0.16145207411437268,
      "sharpe": 0.7476219071402591,
      "maxdd": -0.4147532447392317
    },
    "50000000": {
      "annual": 0.14323255418788297,
      "sharpe": 0.6630034608927662,
      "maxdd": -0.4179765947400599
    },
    "500000000": {
      "annual": 0.13088926248224253,
      "sharpe": 0.6055447319254661,
      "maxdd": -0.42524300542641025
    },
    "2000000000": {
      "annual": 0.12994803727020274,
      "sharpe": 0.6012841262898017,
      "maxdd": -0.42878589438197035
    }
  },
  "capacity_limit_aum": 2000000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- Extreme regime dependency: Bear market return is severely negative: -85.42%

**Key Metrics:**
```json
{
  "wf_annual": 0.1117,
  "wf_sharpe": 0.5451,
  "wf_maxdd": -0.92,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.1402,
  "sharpe_delay_1d": 0.6613,
  "annual_delay_2d": 0.1272,
  "sharpe_delay_2d": 0.6016,
  "bull_annual": 0.9311,
  "bull_sharpe": 4.1867,
  "bear_annual": -0.8542,
  "bear_sharpe": -4.5295
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
  "cv_sharpe": 0.5451,
  "cv_annual": 0.1117,
  "cv_maxdd": -0.92,
  "cv_win_rate": 1.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0007,
  "daily_vol_expected": 0.0136,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0341,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.6188,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
