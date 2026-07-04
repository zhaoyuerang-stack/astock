# Research-to-Production Risk Report: small_cap_factor__window20_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=43.8%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ⚠️ WARN | WARN | Gate 1: Thesis verification complete. Mechanism length=63. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.1125, NW-ICIR=+0.1931, WinRate=77.9%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.5730, Retention=139.0% (Raw NW-ICIR=+0.4123) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.0809 (trials=1), PSR=99.8%, Skew=-0.67, Kurt=16.31 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=16.71%, MaxDD=-38.47%, Sharpe=0.79, Calmar=0.43 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=127.5%. Net Sharpe @ 5M=0.70, @ 50M=0.57, @ 500M=0.49 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.52 (win=100.0%). Delay 1d Sharpe=0.75. Bull Sharpe=4.22, Bear Sharpe=-4.66 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.52 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0663%, Expected Vol=1.3410%. Max Live Drawdown Limit=-57.7% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.438,
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
  "ic_mean": 0.1125,
  "raw_icir": 0.7261,
  "nw_icir": 0.1931,
  "ic_win_rate": 0.7794,
  "ic_count": 3604,
  "quantile_returns": [
    -0.0026,
    0.0046,
    0.01,
    0.0146,
    0.0199
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.04382352174670351,
    "5": 0.07221730349115732,
    "10": 0.09116925222260847,
    "20": 0.11241974335722829
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0877,
  "neut_raw_icir": 0.8835,
  "neut_nw_icir": 0.573,
  "icir_retention": 1.3898
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.0809 after 1 trials

**Key Metrics:**
```json
{
  "skewness": -0.6671,
  "kurtosis": 16.3095,
  "n_periods": 3642,
  "dsr": 1.3994,
  "dsr_p_value": 0.0809,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.9983,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Maximum drawdown exceeds threshold (20.0%): observed=-38.47%
- Sharpe ratio is below target (1.0): observed=0.79

**Key Metrics:**
```json
{
  "annual": 0.1671,
  "maxdd": -0.3847,
  "sharpe": 0.7852,
  "calmar": 0.4345,
  "turnover_annual": 34.0871,
  "cost_annual": 0.1161,
  "sortino": 0.6037,
  "var_95": 0.0196,
  "cvar_95": 0.0353,
  "skew": -0.6673,
  "kurtosis_excess": 13.3294,
  "tail_ratio": 1.0231
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 127.5%
- Capacity limit reached at 500.0M: Net Sharpe=0.49, Return=10.5%

**Key Metrics:**
```json
{
  "annual_1x": 0.1671,
  "annual_2x": 0.0606,
  "annual_3x": -0.0459,
  "cost_decay_rate": 1.2747,
  "capacity_curve": {
    "5000000": {
      "annual": 0.148616406917379,
      "sharpe": 0.6980616414755372,
      "maxdd": -0.3888604669660696
    },
    "50000000": {
      "annual": 0.12071508495098643,
      "sharpe": 0.5662612405308746,
      "maxdd": -0.39500738247809764
    },
    "500000000": {
      "annual": 0.1051966454243483,
      "sharpe": 0.4929576433505089,
      "maxdd": -0.40873191753339944
    },
    "2000000000": {
      "annual": 0.10397755850673568,
      "sharpe": 0.48726436971008413,
      "maxdd": -0.4146204148791792
    }
  },
  "capacity_limit_aum": 500000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- Extreme regime dependency: Bear market return is severely negative: -86.10%

**Key Metrics:**
```json
{
  "wf_annual": 0.1076,
  "wf_sharpe": 0.5245,
  "wf_maxdd": -0.9218,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.1564,
  "sharpe_delay_1d": 0.7457,
  "annual_delay_2d": 0.1454,
  "sharpe_delay_2d": 0.6854,
  "bull_annual": 0.9255,
  "bull_sharpe": 4.2156,
  "bear_annual": -0.861,
  "bear_sharpe": -4.6601
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
  "cv_sharpe": 0.5245,
  "cv_annual": 0.1076,
  "cv_maxdd": -0.9218,
  "cv_win_rate": 1.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0007,
  "daily_vol_expected": 0.0134,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0135,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.577,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
