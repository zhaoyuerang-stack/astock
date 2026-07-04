# Research-to-Production Risk Report: autoresearch_e181a275_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ⚠️ WARN | WARN | Gate 0: Data audit complete. NaN=0.0%, Infs=0, Outliers=126. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=41. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0457, NW-ICIR=+0.0899, WinRate=63.3%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.1899, Retention=111.5% (Raw NW-ICIR=+0.1702) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.2796 (trials=1), PSR=98.4%, Skew=+1.53, Kurt=45.63 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=15.50%, MaxDD=-56.21%, Sharpe=0.55, Calmar=0.28 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=138.3%. Net Sharpe @ 5M=0.52, @ 50M=0.46, @ 500M=0.36 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.31 (win=91.7%). Delay 1d Sharpe=0.48. Bull Sharpe=3.73, Bear Sharpe=-3.89 |
| 7A | Purged + Embargoed CV | ❌ FAIL | FAIL | Gate 7A: CV Sharpe=0.31 (win=91.7%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0615%, Expected Vol=1.7754%. Max Live Drawdown Limit=-84.3% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (⚠️ WARN)
**Reasons/Warnings:**
- Found 126 extreme outliers (>10 std deviations)

**Key Metrics:**
```json
{
  "nan_pct": 0.0,
  "inf_count": 0,
  "outliers_10std": 126,
  "lookahead_pert_diff": 0.0
}
```

### Gate 1: Economic Hypothesis (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "has_thesis": true,
  "thesis_len": 41,
  "citation_len": 26,
  "has_keywords": true
}
```

### Gate 2: Single Factor Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "ic_mean": 0.0457,
  "raw_icir": 0.3304,
  "nw_icir": 0.0899,
  "ic_win_rate": 0.6329,
  "ic_count": 3503,
  "quantile_returns": [
    0.0047,
    0.0083,
    0.011,
    0.0147,
    0.0175
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.021311230742270686,
    "5": 0.034581949051502324,
    "10": 0.040051848909974846,
    "20": 0.045386304481433756
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0323,
  "neut_raw_icir": 0.3607,
  "neut_nw_icir": 0.1899,
  "icir_retention": 1.1155
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.2796 after 1 trials

**Key Metrics:**
```json
{
  "skewness": 1.5252,
  "kurtosis": 45.6348,
  "n_periods": 3642,
  "dsr": 0.584,
  "dsr_p_value": 0.2796,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9836,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Maximum drawdown exceeds threshold (20.0%): observed=-56.21%
- Sharpe ratio is below target (1.0): observed=0.55

**Key Metrics:**
```json
{
  "annual": 0.155,
  "maxdd": -0.5621,
  "sharpe": 0.5501,
  "calmar": 0.2758,
  "turnover_annual": 34.3141,
  "cost_annual": 0.1168,
  "sortino": 0.4526,
  "var_95": 0.0267,
  "cvar_95": 0.0439,
  "skew": 1.5258,
  "kurtosis_excess": 42.6951,
  "tail_ratio": 1.0028
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 138.3%
- Capacity limit reached at 50.0M: Net Sharpe=0.46, Return=13.1%

**Key Metrics:**
```json
{
  "annual_1x": 0.155,
  "annual_2x": 0.0478,
  "annual_3x": -0.0594,
  "cost_decay_rate": 1.3834,
  "capacity_curve": {
    "5000000": {
      "annual": 0.14620134402964086,
      "sharpe": 0.5187855502316595,
      "maxdd": -0.5759174140623498
    },
    "50000000": {
      "annual": 0.1305873039310713,
      "sharpe": 0.46333409633125666,
      "maxdd": -0.5997699867202753
    },
    "500000000": {
      "annual": 0.1024165553674611,
      "sharpe": 0.3630203043087176,
      "maxdd": -0.6404186347630176
    },
    "2000000000": {
      "annual": 0.09092529603454105,
      "sharpe": 0.3220429103664338,
      "maxdd": -0.6580213437483782
    }
  },
  "capacity_limit_aum": 50000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- OOS Walk-Forward aggregate Sharpe is weak (<0.50): observed=0.31
- Extreme regime dependency: Bear market return is severely negative: -104.38%

**Key Metrics:**
```json
{
  "wf_annual": 0.075,
  "wf_sharpe": 0.313,
  "wf_maxdd": -0.986,
  "wf_positive_ratio": 0.9167,
  "annual_delay_1d": 0.1258,
  "sharpe_delay_1d": 0.4843,
  "annual_delay_2d": 0.0676,
  "sharpe_delay_2d": 0.2646,
  "bull_annual": 1.0393,
  "bull_sharpe": 3.7322,
  "bear_annual": -1.0438,
  "bear_sharpe": -3.8866
}
```

### Gate 7A: Purged + Embargoed CV (❌ FAIL)
**Reasons/Warnings:**
- Purged + Embargoed CV Sharpe is too weak: observed=0.31

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": 0.313,
  "cv_annual": 0.075,
  "cv_maxdd": -0.986,
  "cv_win_rate": 0.9167
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0006,
  "daily_vol_expected": 0.0178,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0802,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.8432,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
