# Research-to-Production Risk Report: roc_yc_v1.0
**Run Date**: 2026-07-05 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ✅ PASS | PASS | Gate 0: Data audit complete. NaN=37.5%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ⚠️ WARN | WARN | Gate 1: Thesis verification complete. Mechanism length=135. |
| 2 | Single Factor Verification | ❌ FAIL | FAIL | Gate 2: Rank IC=+0.0003, NW-ICIR=+0.0012, WinRate=49.4%, MonoCorr=-0.10 |
| 3 | Neutralization Verification | ✅ PASS | PASS | Gate 3: Neut NW-ICIR=+0.1207, Retention=9048.8% (Raw NW-ICIR=+0.0013) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.9636 (trials=56), PSR=72.4%, Skew=-0.73, Kurt=9.40 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=6.45%, MaxDD=-53.20%, Sharpe=0.23, Calmar=0.12 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=69.4%. Net Sharpe @ 5M=0.21, @ 50M=0.18, @ 500M=0.12 |
| 7 | Out-of-Sample & Stress Testing | ⚠️ WARN | WARN | Gate 7: WF Sharpe=0.24 (win=75.0%). Delay 1d Sharpe=0.15. Bull Sharpe=4.42, Bear Sharpe=-3.61 |
| 7A | Purged + Embargoed CV | ❌ FAIL | FAIL | Gate 7A: CV Sharpe=0.24 (win=75.0%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=0.0256%, Expected Vol=1.7673%. Max Live Drawdown Limit=-79.8% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "nan_pct": 0.3745,
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
  "thesis_len": 135,
  "citation_len": 60,
  "has_keywords": false
}
```

### Gate 2: Single Factor Verification (❌ FAIL)
**Reasons/Warnings:**
- NW-ICIR is below minimum threshold (0.03): observed=0.0012
- Weak monotonicity across 5 factor quantiles: Spearman corr=-0.10

**Key Metrics:**
```json
{
  "ic_mean": 0.0003,
  "raw_icir": 0.0045,
  "nw_icir": 0.0012,
  "ic_win_rate": 0.494,
  "ic_count": 1409,
  "quantile_returns": [
    0.0104,
    0.0105,
    0.0112,
    0.0107,
    0.0094
  ],
  "monotonicity_corr": -0.1,
  "ic_decay": {
    "1": 0.0014765788837847289,
    "5": 0.00040894674371014754,
    "10": 0.00023743908309929084,
    "20": 0.00014979965486564448
  }
}
```

### Gate 3: Neutralization Verification (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "neut_ic_mean": -0.0072,
  "neut_raw_icir": -0.2306,
  "neut_nw_icir": 0.1207,
  "icir_retention": 90.4876
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.9636 after 56 trials
- Probabilistic Sharpe Ratio (Sharpe>0) is too low: PSR=72.4% (target >= 95.0%)

**Key Metrics:**
```json
{
  "skewness": -0.7306,
  "kurtosis": 9.396,
  "n_periods": 1698,
  "dsr": -1.7935,
  "dsr_p_value": 0.9636,
  "e_max_sr": 1.3995,
  "dsr_significant": false,
  "psr": 0.7235,
  "n_trials": 56
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=6.45%
- Maximum drawdown exceeds threshold (20.0%): observed=-53.20%
- Sharpe ratio is below target (1.0): observed=0.23

**Key Metrics:**
```json
{
  "annual": 0.0645,
  "maxdd": -0.532,
  "sharpe": 0.2299,
  "calmar": 0.1212,
  "turnover_annual": 7.1771,
  "cost_annual": 0.036,
  "sortino": 0.1939,
  "var_95": 0.0272,
  "cvar_95": 0.0451,
  "skew": -0.7313,
  "kurtosis_excess": 6.4185,
  "tail_ratio": 1.0049
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 69.4%
- Capacity limit reached at 5.0M: Net Sharpe=0.21, Return=6.0%

**Key Metrics:**
```json
{
  "annual_1x": 0.0645,
  "annual_2x": 0.0421,
  "annual_3x": 0.0197,
  "cost_decay_rate": 0.6941,
  "capacity_curve": {
    "5000000": {
      "annual": 0.05958946375318226,
      "sharpe": 0.21237932466836693,
      "maxdd": -0.5381998852552532
    },
    "50000000": {
      "annual": 0.05053545096066242,
      "sharpe": 0.18005837170388914,
      "maxdd": -0.5493063966022914
    },
    "500000000": {
      "annual": 0.033367401911163476,
      "sharpe": 0.11877898878679127,
      "maxdd": -0.5703523400658265
    },
    "2000000000": {
      "annual": 0.02480688426263184,
      "sharpe": 0.08825070034808752,
      "maxdd": -0.5802537341003885
    }
  },
  "capacity_limit_aum": 5000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (⚠️ WARN)
**Reasons/Warnings:**
- OOS Walk-Forward aggregate Sharpe is weak (<0.50): observed=0.24
- Extreme regime dependency: Bear market return is severely negative: -112.04%

**Key Metrics:**
```json
{
  "wf_annual": 0.0806,
  "wf_sharpe": 0.245,
  "wf_maxdd": -0.8346,
  "wf_positive_ratio": 0.75,
  "annual_delay_1d": 0.0415,
  "sharpe_delay_1d": 0.1483,
  "annual_delay_2d": 0.0386,
  "sharpe_delay_2d": 0.1426,
  "bull_annual": 1.0453,
  "bull_sharpe": 4.4186,
  "bear_annual": -1.1204,
  "bear_sharpe": -3.6142
}
```

### Gate 7A: Purged + Embargoed CV (❌ FAIL)
**Reasons/Warnings:**
- Purged + Embargoed CV Sharpe is too weak: observed=0.24

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": 0.245,
  "cv_annual": 0.0806,
  "cv_maxdd": -0.8346,
  "cv_win_rate": 0.75
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": 0.0003,
  "daily_vol_expected": 0.0177,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.1257,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -0.798,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
