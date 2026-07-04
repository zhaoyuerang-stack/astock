# Research-to-Production Risk Report: autoresearch_8de70997_v1.0
**Run Date**: 2026-07-03 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=0.0%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=41. |
| 2 | Single Factor Verification | ✅ PASS | PASS | Gate 2: Rank IC=+0.0433, NW-ICIR=+0.0796, WinRate=61.5%, MonoCorr=1.00 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.1921, Retention=120.2% (Raw NW-ICIR=+0.1598) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.4259 (trials=1), PSR=65.3%, Skew=+0.07, Kurt=16.66 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=2.79%, MaxDD=-70.11%, Sharpe=0.10, Calmar=0.04 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=741.3%. Net Sharpe @ 5M=0.08, @ 50M=0.04, @ 500M=-0.04 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.15 (win=66.7%). Delay 1d Sharpe=-0.08. Bull Sharpe=3.18, Bear Sharpe=-5.21 |
| 7A | Purged + Embargoed CV | ❌ FAIL | FAIL | Gate 7A: CV Sharpe=0.15 (win=66.7%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0111%, Expected Vol=1.7036%. Max Live Drawdown Limit=-105.2% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.0,
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
  "ic_mean": 0.0433,
  "raw_icir": 0.2925,
  "nw_icir": 0.0796,
  "ic_win_rate": 0.6155,
  "ic_count": 3503,
  "quantile_returns": [
    0.0039,
    0.01,
    0.0121,
    0.0128,
    0.0193
  ],
  "monotonicity_corr": 1.0,
  "ic_decay": {
    "1": 0.020438954082417003,
    "5": 0.03450641992013909,
    "10": 0.03923369042158497,
    "20": 0.04292266847123848
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0352,
  "neut_raw_icir": 0.3441,
  "neut_nw_icir": 0.1921,
  "icir_retention": 1.2024
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.4259 after 1 trials
- Probabilistic Sharpe Ratio (Sharpe>0) is too low: PSR=65.3% (target >= 95.0%)

**Key Metrics:**
```json
{
  "skewness": 0.0662,
  "kurtosis": 16.6559,
  "n_periods": 3642,
  "dsr": 0.1869,
  "dsr_p_value": 0.4259,
  "e_max_sr": 0.0,
  "dsr_significant": false,
  "psr": 0.6527,
  "n_trials": 1
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=2.79%
- Maximum drawdown exceeds threshold (20.0%): observed=-70.11%
- Sharpe ratio is below target (1.0): observed=0.10

**Key Metrics:**
```json
{
  "annual": 0.0279,
  "maxdd": -0.7011,
  "sharpe": 0.1033,
  "calmar": 0.0398,
  "turnover_annual": 33.135,
  "cost_annual": 0.1131,
  "sortino": 0.0826,
  "var_95": 0.0264,
  "cvar_95": 0.0439,
  "skew": 0.0662,
  "kurtosis_excess": 13.6763,
  "tail_ratio": 0.9536
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 741.3%
- Capacity limit reached at 5.0M: Net Sharpe=0.08, Return=2.2%

**Key Metrics:**
```json
{
  "annual_1x": 0.0279,
  "annual_2x": -0.0756,
  "annual_3x": -0.1792,
  "cost_decay_rate": 7.4134,
  "capacity_curve": {
    "5000000": {
      "annual": 0.02162000764973137,
      "sharpe": 0.07995387566315322,
      "maxdd": -0.7130211068307994
    },
    "50000000": {
      "annual": 0.010132987499944655,
      "sharpe": 0.037476128154620515,
      "maxdd": -0.7341424180631779
    },
    "500000000": {
      "annual": -0.011069014645662527,
      "sharpe": -0.04092732711297684,
      "maxdd": -0.7728034947970313
    },
    "2000000000": {
      "annual": -0.021562099106967422,
      "sharpe": -0.07970013027843144,
      "maxdd": -0.7953041873350774
    }
  },
  "capacity_limit_aum": 5000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- OOS Walk-Forward aggregate Sharpe is weak (<0.50): observed=0.15
- Extreme regime dependency: Bear market return is severely negative: -117.21%

**Key Metrics:**
```json
{
  "wf_annual": 0.0349,
  "wf_sharpe": 0.1517,
  "wf_maxdd": -0.9959,
  "wf_positive_ratio": 0.6667,
  "annual_delay_1d": -0.021,
  "sharpe_delay_1d": -0.08,
  "annual_delay_2d": -0.0434,
  "sharpe_delay_2d": -0.1697,
  "bull_annual": 0.913,
  "bull_sharpe": 3.1805,
  "bear_annual": -1.1721,
  "bear_sharpe": -5.2068
}
```

### Gate 7A: Purged + Embargoed CV (❌ FAIL)
**Reasons/Warnings:**
- Purged + Embargoed CV Sharpe is too weak: observed=0.15

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": 0.1517,
  "cv_annual": 0.0349,
  "cv_maxdd": -0.9959,
  "cv_win_rate": 0.6667
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0001,
  "daily_vol_expected": 0.017,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.0827,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -1.0516,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
