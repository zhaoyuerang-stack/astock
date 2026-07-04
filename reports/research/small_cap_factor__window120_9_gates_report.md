# Research-to-Production Risk Report: small_cap_factor__window120_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ⚠️ WARN | WARN | Gate 0: Data audit complete. NaN=54.9%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ⚠️ WARN | WARN | Gate 1: Thesis verification complete. Mechanism length=64. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0801, NW-ICIR=+0.1352, WinRate=71.2%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.2722, Retention=92.9% (Raw NW-ICIR=+0.2931) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.0946 (trials=1), PSR=99.8%, Skew=-0.81, Kurt=18.06 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=17.13%, MaxDD=-44.76%, Sharpe=0.78, Calmar=0.38 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=105.0%. Net Sharpe @ 5M=0.74, @ 50M=0.69, @ 500M=0.64 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.53 (win=100.0%). Delay 1d Sharpe=0.61. Bull Sharpe=4.02, Bear Sharpe=-4.32 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.53 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0680%, Expected Vol=1.3844%. Max Live Drawdown Limit=-67.1% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (⚠️ WARN)
**Reasons/Warnings:**
- High missing data: 54.9% of factor panel is NaN

**Key Metrics:**
```json
{
  "nan_pct": 0.5492,
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
  "ic_mean": 0.0801,
  "raw_icir": 0.5063,
  "nw_icir": 0.1352,
  "ic_win_rate": 0.7123,
  "ic_count": 3403,
  "quantile_returns": [
    0.0019,
    0.0055,
    0.0087,
    0.0134,
    0.0179
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.027618203887808734,
    "5": 0.04887286588338231,
    "10": 0.06364382972087279,
    "20": 0.08125898124134844
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0474,
  "neut_raw_icir": 0.5235,
  "neut_nw_icir": 0.2722,
  "icir_retention": 0.9288
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.0946 after 1 trials

**Key Metrics:**
```json
{
  "skewness": -0.814,
  "kurtosis": 18.0602,
  "n_periods": 3642,
  "dsr": 1.3129,
  "dsr_p_value": 0.0946,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9981,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Maximum drawdown exceeds threshold (20.0%): observed=-44.76%
- Sharpe ratio is below target (1.0): observed=0.78

**Key Metrics:**
```json
{
  "annual": 0.1713,
  "maxdd": -0.4476,
  "sharpe": 0.7796,
  "calmar": 0.3828,
  "turnover_annual": 28.7842,
  "cost_annual": 0.099,
  "sortino": 0.5862,
  "var_95": 0.0187,
  "cvar_95": 0.036,
  "skew": -0.8144,
  "kurtosis_excess": 15.0826,
  "tail_ratio": 1.1195
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 105.0%

**Key Metrics:**
```json
{
  "annual_1x": 0.1713,
  "annual_2x": 0.0814,
  "annual_3x": -0.0086,
  "cost_decay_rate": 1.05,
  "capacity_curve": {
    "5000000": {
      "annual": 0.16325329994187832,
      "sharpe": 0.7428297631758258,
      "maxdd": -0.44880707146099685
    },
    "50000000": {
      "annual": 0.15068265667510483,
      "sharpe": 0.6854401439613199,
      "maxdd": -0.4506229796516511
    },
    "500000000": {
      "annual": 0.14121198817920044,
      "sharpe": 0.6421491442200429,
      "maxdd": -0.4547009807738438
    },
    "2000000000": {
      "annual": 0.14021762869293802,
      "sharpe": 0.6377235252632868,
      "maxdd": -0.45757408158294044
    }
  },
  "capacity_limit_aum": 2000000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- Extreme regime dependency: Bear market return is severely negative: -83.20%

**Key Metrics:**
```json
{
  "wf_annual": 0.1094,
  "wf_sharpe": 0.5265,
  "wf_maxdd": -0.9389,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.1317,
  "sharpe_delay_1d": 0.613,
  "annual_delay_2d": 0.122,
  "sharpe_delay_2d": 0.5774,
  "bull_annual": 0.9114,
  "bull_sharpe": 4.0183,
  "bear_annual": -0.832,
  "bear_sharpe": -4.3181
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
  "cv_sharpe": 0.5265,
  "cv_annual": 0.1094,
  "cv_maxdd": -0.9389,
  "cv_win_rate": 1.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0007,
  "daily_vol_expected": 0.0138,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0459,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.6714,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
