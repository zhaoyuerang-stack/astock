# Research-to-Production Risk Report: autoresearch_234c8ab7_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ⚠️ WARN | WARN | Gate 0: Data audit complete. NaN=0.0%, Infs=0, Outliers=353. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=57. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0558, NW-ICIR=+0.1021, WinRate=65.1%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.3374, Retention=146.2% (Raw NW-ICIR=+0.2308) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.3380 (trials=1), PSR=80.8%, Skew=-0.72, Kurt=15.46 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=5.52%, MaxDD=-44.55%, Sharpe=0.23, Calmar=0.12 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=365.2%. Net Sharpe @ 5M=0.22, @ 50M=0.21, @ 500M=0.19 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.17 (win=75.0%). Delay 1d Sharpe=0.22. Bull Sharpe=3.35, Bear Sharpe=-4.73 |
| 7A | Purged + Embargoed CV | ❌ FAIL | FAIL | Gate 7A: CV Sharpe=0.17 (win=75.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0219%, Expected Vol=1.5101%. Max Live Drawdown Limit=-66.8% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (⚠️ WARN)
**Reasons/Warnings:**
- Found 353 extreme outliers (>10 std deviations)

**Key Metrics:**
```json
{
  "nan_pct": 0.0,
  "inf_count": 0,
  "outliers_10std": 353,
  "lookahead_pert_diff": 0.0
}
```

### Gate 1: Economic Hypothesis (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "has_thesis": true,
  "thesis_len": 57,
  "citation_len": 26,
  "has_keywords": true
}
```

### Gate 2: Single Factor Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "ic_mean": 0.0558,
  "raw_icir": 0.3678,
  "nw_icir": 0.1021,
  "ic_win_rate": 0.6506,
  "ic_count": 3563,
  "quantile_returns": [
    0.0017,
    0.0093,
    0.011,
    0.0113,
    0.0128
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.027945586849786142,
    "5": 0.03586754948648078,
    "10": 0.045022728640689645,
    "20": 0.05580057102407222
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0582,
  "neut_raw_icir": 0.5759,
  "neut_nw_icir": 0.3374,
  "icir_retention": 1.4621
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.3380 after 1 trials
- Probabilistic Sharpe Ratio (Sharpe>0) is too low: PSR=80.8% (target >= 95.0%)

**Key Metrics:**
```json
{
  "skewness": -0.7249,
  "kurtosis": 15.4609,
  "n_periods": 3642,
  "dsr": 0.4181,
  "dsr_p_value": 0.338,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.8078,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=5.52%
- Maximum drawdown exceeds threshold (20.0%): observed=-44.55%
- Sharpe ratio is below target (1.0): observed=0.23

**Key Metrics:**
```json
{
  "annual": 0.0552,
  "maxdd": -0.4455,
  "sharpe": 0.2301,
  "calmar": 0.1238,
  "turnover_annual": 32.2328,
  "cost_annual": 0.1103,
  "sortino": 0.1768,
  "var_95": 0.0221,
  "cvar_95": 0.0398,
  "skew": -0.7252,
  "kurtosis_excess": 12.4797,
  "tail_ratio": 1.0473
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 365.2%
- Capacity limit reached at 5.0M: Net Sharpe=0.22, Return=5.4%

**Key Metrics:**
```json
{
  "annual_1x": 0.0552,
  "annual_2x": -0.0456,
  "annual_3x": -0.1463,
  "cost_decay_rate": 3.6524,
  "capacity_curve": {
    "5000000": {
      "annual": 0.05359898475327339,
      "sharpe": 0.22360832582517734,
      "maxdd": -0.44549690255826124
    },
    "50000000": {
      "annual": 0.050739399128967425,
      "sharpe": 0.21170695265423572,
      "maxdd": -0.4455975420740441
    },
    "500000000": {
      "annual": 0.045428641591776654,
      "sharpe": 0.18958393664323744,
      "maxdd": -0.4458851119156598
    },
    "2000000000": {
      "annual": 0.04254512860311152,
      "sharpe": 0.17757084904189882,
      "maxdd": -0.4548940238570207
    }
  },
  "capacity_limit_aum": 5000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- OOS Walk-Forward aggregate Sharpe is weak (<0.50): observed=0.17
- Extreme regime dependency: Bear market return is severely negative: -99.73%

**Key Metrics:**
```json
{
  "wf_annual": 0.0373,
  "wf_sharpe": 0.1745,
  "wf_maxdd": -0.9916,
  "wf_positive_ratio": 0.75,
  "annual_delay_1d": 0.0501,
  "sharpe_delay_1d": 0.2154,
  "annual_delay_2d": 0.086,
  "sharpe_delay_2d": 0.3818,
  "bull_annual": 0.8314,
  "bull_sharpe": 3.3526,
  "bear_annual": -0.9973,
  "bear_sharpe": -4.7334
}
```

### Gate 7A: Purged + Embargoed CV (❌ FAIL)
**Reasons/Warnings:**
- Purged + Embargoed CV Sharpe is too weak: observed=0.17

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": 0.1745,
  "cv_annual": 0.0373,
  "cv_maxdd": -0.9916,
  "cv_win_rate": 0.75
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0002,
  "daily_vol_expected": 0.0151,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0702,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.6682,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
