# Research-to-Production Risk Report: size_earnings_v1.0
**Run Date**: 2026-07-05 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=28.7%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=67. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0511, NW-ICIR=+0.1372, WinRate=70.3%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.4728, Retention=119.1% (Raw NW-ICIR=+0.3971) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.5973 (trials=3), PSR=90.0%, Skew=+0.34, Kurt=16.59 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=8.94%, MaxDD=-30.82%, Sharpe=0.49, Calmar=0.29 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=202.6%. Net Sharpe @ 5M=0.49, @ 50M=0.48, @ 500M=0.44 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.51 (win=100.0%). Delay 1d Sharpe=0.48. Bull Sharpe=3.66, Bear Sharpe=-4.85 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.51 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0355%, Expected Vol=1.1425%. Max Live Drawdown Limit=-46.2% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.2875,
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
  "thesis_len": 67,
  "citation_len": 28,
  "has_keywords": true
}
```

### Gate 2: Single Factor Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "ic_mean": 0.0511,
  "raw_icir": 0.4896,
  "nw_icir": 0.1372,
  "ic_win_rate": 0.7031,
  "ic_count": 1620,
  "quantile_returns": [
    0.0031,
    0.0055,
    0.007,
    0.0095,
    0.0107
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.013604630046142971,
    "5": 0.032112626817246796,
    "10": 0.04037058546322596,
    "20": 0.05086796394068845
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0381,
  "neut_raw_icir": 0.6421,
  "neut_nw_icir": 0.4728,
  "icir_retention": 1.1906
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.5973 after 3 trials
- Probabilistic Sharpe Ratio (Sharpe>0) is too low: PSR=90.0% (target >= 95.0%)

**Key Metrics:**
```json
{
  "skewness": 0.3408,
  "kurtosis": 16.5939,
  "n_periods": 1698,
  "dsr": -0.2465,
  "dsr_p_value": 0.5973,
  "e_max_sr": 0.6936,
  "dsr_significant": false,
  "psr": 0.9004,
  "n_trials": 3
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=8.94%
- Maximum drawdown exceeds threshold (20.0%): observed=-30.82%
- Sharpe ratio is below target (1.0): observed=0.49

**Key Metrics:**
```json
{
  "annual": 0.0894,
  "maxdd": -0.3082,
  "sharpe": 0.4931,
  "calmar": 0.2902,
  "turnover_annual": 28.9853,
  "cost_annual": 0.0997,
  "sortino": 0.3899,
  "var_95": 0.0176,
  "cvar_95": 0.0285,
  "skew": 0.3411,
  "kurtosis_excess": 13.6376,
  "tail_ratio": 1.0564
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 202.6%
- Capacity limit reached at 5.0M: Net Sharpe=0.49, Return=8.8%

**Key Metrics:**
```json
{
  "annual_1x": 0.0894,
  "annual_2x": -0.0011,
  "annual_3x": -0.0917,
  "cost_decay_rate": 2.0256,
  "capacity_curve": {
    "5000000": {
      "annual": 0.08847528865627008,
      "sharpe": 0.4878526165365978,
      "maxdd": -0.30913104755557197
    },
    "50000000": {
      "annual": 0.08640470044820667,
      "sharpe": 0.4764677176211896,
      "maxdd": -0.3111615416368926
    },
    "500000000": {
      "annual": 0.08002062854695306,
      "sharpe": 0.4413068888844946,
      "maxdd": -0.3174071919468251
    },
    "2000000000": {
      "annual": 0.07217970542341916,
      "sharpe": 0.3980232322136604,
      "maxdd": -0.3251329484157808
    }
  },
  "capacity_limit_aum": 5000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- Extreme regime dependency: Bear market return is severely negative: -67.86%

**Key Metrics:**
```json
{
  "wf_annual": 0.0994,
  "wf_sharpe": 0.512,
  "wf_maxdd": -0.6116,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.088,
  "sharpe_delay_1d": 0.479,
  "annual_delay_2d": 0.1064,
  "sharpe_delay_2d": 0.5704,
  "bull_annual": 0.7358,
  "bull_sharpe": 3.6556,
  "bear_annual": -0.6786,
  "bear_sharpe": -4.8523
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
  "cv_sharpe": 0.512,
  "cv_annual": 0.0994,
  "cv_maxdd": -0.6116,
  "cv_win_rate": 1.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0004,
  "daily_vol_expected": 0.0114,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0749,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.4623,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
