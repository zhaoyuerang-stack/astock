# Research-to-Production Risk Report: small_cap_factor__window90_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ⚠️ WARN | WARN | Gate 0: Data audit complete. NaN=52.4%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ⚠️ WARN | WARN | Gate 1: Thesis verification complete. Mechanism length=63. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0848, NW-ICIR=+0.1442, WinRate=72.8%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.3278, Retention=105.8% (Raw NW-ICIR=+0.3099) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.0672 (trials=1), PSR=99.9%, Skew=-0.66, Kurt=17.07 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=18.78%, MaxDD=-42.87%, Sharpe=0.86, Calmar=0.44 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=102.5%. Net Sharpe @ 5M=0.81, @ 50M=0.74, @ 500M=0.69 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.55 (win=100.0%). Delay 1d Sharpe=0.77. Bull Sharpe=4.26, Bear Sharpe=-4.55 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.55 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0745%, Expected Vol=1.3810%. Max Live Drawdown Limit=-64.3% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (⚠️ WARN)
**Reasons/Warnings:**
- High missing data: 52.4% of factor panel is NaN

**Key Metrics:**
```json
{
  "nan_pct": 0.5237,
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
  "ic_mean": 0.0848,
  "raw_icir": 0.5402,
  "nw_icir": 0.1442,
  "ic_win_rate": 0.7282,
  "ic_count": 3510,
  "quantile_returns": [
    0.0015,
    0.0043,
    0.0088,
    0.0134,
    0.0178
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.02918467103886032,
    "5": 0.051313938484095316,
    "10": 0.06710236876864914,
    "20": 0.08530862086396539
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0558,
  "neut_raw_icir": 0.5836,
  "neut_nw_icir": 0.3278,
  "icir_retention": 1.0576
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.0672 after 1 trials

**Key Metrics:**
```json
{
  "skewness": -0.6577,
  "kurtosis": 17.0725,
  "n_periods": 3642,
  "dsr": 1.4967,
  "dsr_p_value": 0.0672,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9993,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Maximum drawdown exceeds threshold (20.0%): observed=-42.87%
- Sharpe ratio is below target (1.0): observed=0.86

**Key Metrics:**
```json
{
  "annual": 0.1878,
  "maxdd": -0.4287,
  "sharpe": 0.8566,
  "calmar": 0.4381,
  "turnover_annual": 30.7991,
  "cost_annual": 0.1056,
  "sortino": 0.6529,
  "var_95": 0.0194,
  "cvar_95": 0.0356,
  "skew": -0.658,
  "kurtosis_excess": 14.0935,
  "tail_ratio": 1.0998
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 102.5%

**Key Metrics:**
```json
{
  "annual_1x": 0.1878,
  "annual_2x": 0.0915,
  "annual_3x": -0.0047,
  "cost_decay_rate": 1.025,
  "capacity_curve": {
    "5000000": {
      "annual": 0.1780672033625978,
      "sharpe": 0.8116401956977377,
      "maxdd": -0.43094417782020167
    },
    "50000000": {
      "annual": 0.16294345094127644,
      "sharpe": 0.7415947856866973,
      "maxdd": -0.43428440971642246
    },
    "500000000": {
      "annual": 0.1515078073772359,
      "sharpe": 0.6880641603818621,
      "maxdd": -0.44168981679175046
    },
    "2000000000": {
      "annual": 0.1504837855659407,
      "sharpe": 0.6829270751175464,
      "maxdd": -0.4460228854639383
    }
  },
  "capacity_limit_aum": 2000000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- Extreme regime dependency: Bear market return is severely negative: -86.55%

**Key Metrics:**
```json
{
  "wf_annual": 0.1158,
  "wf_sharpe": 0.5517,
  "wf_maxdd": -0.9398,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.165,
  "sharpe_delay_1d": 0.7686,
  "annual_delay_2d": 0.1587,
  "sharpe_delay_2d": 0.7432,
  "bull_annual": 0.9647,
  "bull_sharpe": 4.2636,
  "bear_annual": -0.8655,
  "bear_sharpe": -4.5493
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
  "cv_sharpe": 0.5517,
  "cv_annual": 0.1158,
  "cv_maxdd": -0.9398,
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
  "live_ic_lower_limit": -0.0412,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.643,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
