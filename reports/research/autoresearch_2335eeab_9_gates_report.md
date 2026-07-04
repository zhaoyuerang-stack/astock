# Research-to-Production Risk Report: autoresearch_2335eeab_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ⚠️ WARN | WARN | Gate 0: Data audit complete. NaN=0.0%, Infs=0, Outliers=3387. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=57. |
| 2 | Single Factor Verification | ⚠️ WARN | WARN | Gate 2: Rank IC=+0.0174, NW-ICIR=+0.0560, WinRate=59.6%, MonoCorr=0.70 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.0879, Retention=75.8% (Raw NW-ICIR=+0.1160) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.1496 (trials=1), PSR=97.5%, Skew=-0.99, Kurt=11.82 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=12.18%, MaxDD=-43.83%, Sharpe=0.52, Calmar=0.28 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=157.5%. Net Sharpe @ 5M=0.51, @ 50M=0.49, @ 500M=0.44 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.41 (win=100.0%). Delay 1d Sharpe=0.50. Bull Sharpe=4.11, Bear Sharpe=-4.87 |
| 7A | Purged + Embargoed CV | ✅ PASS | PASS | Gate 7A: CV Sharpe=0.41 (win=100.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0483%, Expected Vol=1.4625%. Max Live Drawdown Limit=-65.7% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (⚠️ WARN)
**Reasons/Warnings:**
- Found 3387 extreme outliers (>10 std deviations)

**Key Metrics:**
```json
{
  "nan_pct": 0.0,
  "inf_count": 0,
  "outliers_10std": 3387,
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

### Gate 2: Single Factor Verification (⚠️ WARN)
**Reasons/Warnings:**
- Weak monotonicity across 5 factor quantiles: Spearman corr=0.70

**Key Metrics:**
```json
{
  "ic_mean": 0.0174,
  "raw_icir": 0.2113,
  "nw_icir": 0.056,
  "ic_win_rate": 0.5962,
  "ic_count": 3341,
  "quantile_returns": [
    0.0054,
    0.0104,
    0.0121,
    0.0126,
    0.012
  ],
  "monotonicity_corr": 0.7,
  "ic_decay": {
    "1": 0.006647821182459079,
    "5": 0.011276141571501556,
    "10": 0.014721972308912427,
    "20": 0.017575208885703936
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0072,
  "neut_raw_icir": 0.1494,
  "neut_nw_icir": 0.0879,
  "icir_retention": 0.7579
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.1496 after 1 trials

**Key Metrics:**
```json
{
  "skewness": -0.9863,
  "kurtosis": 11.8183,
  "n_periods": 3642,
  "dsr": 1.038,
  "dsr_p_value": 0.1496,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.975,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=12.18%
- Maximum drawdown exceeds threshold (20.0%): observed=-43.83%
- Sharpe ratio is below target (1.0): observed=0.52

**Key Metrics:**
```json
{
  "annual": 0.1218,
  "maxdd": -0.4383,
  "sharpe": 0.5246,
  "calmar": 0.2779,
  "turnover_annual": 30.6884,
  "cost_annual": 0.1055,
  "sortino": 0.395,
  "var_95": 0.0217,
  "cvar_95": 0.0393,
  "skew": -0.9867,
  "kurtosis_excess": 8.832,
  "tail_ratio": 1.0587
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 157.5%
- Capacity limit reached at 50.0M: Net Sharpe=0.49, Return=11.3%

**Key Metrics:**
```json
{
  "annual_1x": 0.1218,
  "annual_2x": 0.0259,
  "annual_3x": -0.07,
  "cost_decay_rate": 1.5749,
  "capacity_curve": {
    "5000000": {
      "annual": 0.11844582395544673,
      "sharpe": 0.5101783502374247,
      "maxdd": -0.44130425448711885
    },
    "50000000": {
      "annual": 0.1126658064920912,
      "sharpe": 0.4852107158078276,
      "maxdd": -0.44612382495448377
    },
    "500000000": {
      "annual": 0.10334943745011832,
      "sharpe": 0.4448736428112145,
      "maxdd": -0.46834940738285646
    },
    "2000000000": {
      "annual": 0.09985871300870133,
      "sharpe": 0.4297058249283375,
      "maxdd": -0.4787861732523031
    }
  },
  "capacity_limit_aum": 50000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- OOS Walk-Forward aggregate Sharpe is weak (<0.50): observed=0.41
- Extreme regime dependency: Bear market return is severely negative: -101.79%

**Key Metrics:**
```json
{
  "wf_annual": 0.0892,
  "wf_sharpe": 0.4064,
  "wf_maxdd": -0.9777,
  "wf_positive_ratio": 1.0,
  "annual_delay_1d": 0.1127,
  "sharpe_delay_1d": 0.497,
  "annual_delay_2d": 0.1007,
  "sharpe_delay_2d": 0.4525,
  "bull_annual": 0.9624,
  "bull_sharpe": 4.11,
  "bear_annual": -1.0179,
  "bear_sharpe": -4.8696
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
  "cv_sharpe": 0.4064,
  "cv_annual": 0.0892,
  "cv_maxdd": -0.9777,
  "cv_win_rate": 1.0
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0005,
  "daily_vol_expected": 0.0146,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.1086,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.6574,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
