# Research-to-Production Risk Report: hq_momentum_v1.0-full
**Run Date**: 2026-07-05 | **Overall Verdict**: ❌ REJECTED (GATES FAILED)

## Executive Summary of Gates
| Gate | Name | Status | Verdict | Details |
| --- | --- | --- | --- | --- |
| 0 | Data Audit | ❌ FAIL | FAIL | Gate 0: Data audit complete. NaN=94.6%, Infs=0, Outliers=0. Perturbation diff=0.000000 |
| 1 | Economic Hypothesis | ✅ PASS | PASS | Gate 1: Thesis verification complete. Mechanism length=44. |
| 2 | Single Factor Verification | ❌ FAIL | FAIL | Gate 2: Rank IC=-0.0107, NW-ICIR=+0.0232, WinRate=52.5%, MonoCorr=0.90 |
| 3 | Neutralization Verification | ❌ FAIL | FAIL | Gate 3: Neut NW-ICIR=+0.0161, Retention=29.5% (Raw NW-ICIR=+0.0546) |
| 4 | Multiple Testing Penalty | ❌ FAIL | FAIL | Gate 4: DSR p-val=0.8840 (trials=3), PSR=31.9%, Skew=-0.57, Kurt=5.83 |
| 5 | Portfolio Backtesting | ❌ FAIL | FAIL | Gate 5: Annualized Return=-4.68%, MaxDD=-94.16%, Sharpe=-0.13, Calmar=-0.05 |
| 6 | Cost & Capacity Modeling | ❌ FAIL | FAIL | Gate 6: Cost Decay=100.0%. Net Sharpe @ 5M=-0.19, @ 50M=-0.25, @ 500M=-0.29 |
| 7 | Out-of-Sample & Stress Testing | ❌ FAIL | FAIL | Gate 7: WF Sharpe=-0.09 (win=41.7%). Delay 1d Sharpe=-0.13. Bull Sharpe=3.56, Bear Sharpe=-4.13 |
| 7A | Purged + Embargoed CV | ❌ FAIL | FAIL | Gate 7A: CV Sharpe=-0.09 (win=41.7%), Purge=20d, Embargo=20d |
| 8 | Live Monitoring | ✅ PASS | PASS | Gate 8: Live tracking profile constructed. Daily expected mean=-0.0186%, Expected Vol=2.2251%. Max Live Drawdown Limit=-141.2% |

## Detailed Gate Findings & Failures
### Gate 0: Data Audit (❌ FAIL)
**Reasons/Warnings:**
- Extremely high missing data: 94.6% of factor panel is NaN

**Key Metrics:**
```json
{
  "nan_pct": 0.9461,
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
  "thesis_len": 44,
  "citation_len": 28,
  "has_keywords": true
}
```

### Gate 2: Single Factor Verification (❌ FAIL)
**Reasons/Warnings:**
- NW-ICIR is below minimum threshold (0.03): observed=0.0232

**Key Metrics:**
```json
{
  "ic_mean": -0.0107,
  "raw_icir": -0.0775,
  "nw_icir": 0.0232,
  "ic_win_rate": 0.5251,
  "ic_count": 3308,
  "quantile_returns": [
    0.0022,
    0.0044,
    0.0044,
    0.005,
    0.0047
  ],
  "monotonicity_corr": 0.9,
  "ic_decay": {
    "1": -0.004733167796322481,
    "5": -0.012093866632405085,
    "10": -0.013174476984703545,
    "20": -0.0121422914243558
  }
}
```

### Gate 3: Neutralization Verification (❌ FAIL)
**Reasons/Warnings:**
- Neutralized NW-ICIR is too low (<0.02): observed=0.0161

**Key Metrics:**
```json
{
  "neut_ic_mean": 0.0011,
  "neut_raw_icir": 0.024,
  "neut_nw_icir": 0.0161,
  "icir_retention": 0.2954
}
```

### Gate 4: Multiple Testing Penalty (❌ FAIL)
**Reasons/Warnings:**
- Deflated Sharpe p-value is not significant (>0.05): p=0.8840 after 3 trials
- Probabilistic Sharpe Ratio (Sharpe>0) is too low: PSR=31.9% (target >= 95.0%)

**Key Metrics:**
```json
{
  "skewness": -0.5715,
  "kurtosis": 5.8307,
  "n_periods": 3156,
  "dsr": -1.1953,
  "dsr_p_value": 0.884,
  "e_max_sr": 0.3296,
  "dsr_significant": false,
  "psr": 0.3193,
  "n_trials": 3
}
```

### Gate 5: Portfolio Backtesting (❌ FAIL)
**Reasons/Warnings:**
- Annualized return is below target (15.0%): observed=-4.68%
- Maximum drawdown exceeds threshold (20.0%): observed=-94.16%
- Sharpe ratio is below target (1.0): observed=-0.13

**Key Metrics:**
```json
{
  "annual": -0.0468,
  "maxdd": -0.9416,
  "sharpe": -0.1324,
  "calmar": -0.0497,
  "turnover_annual": 15.12,
  "cost_annual": 0.0635,
  "sortino": -0.1223,
  "var_95": 0.0363,
  "cvar_95": 0.0566,
  "skew": -0.5718,
  "kurtosis_excess": 2.8371,
  "tail_ratio": 0.8989
}
```

### Gate 6: Cost & Capacity Modeling (❌ FAIL)
**Reasons/Warnings:**
- High transaction cost sensitivity: 3x costs degrade returns by 100.0%
- Capacity limit reached at 5.0M: Net Sharpe=-0.19, Return=-6.6%

**Key Metrics:**
```json
{
  "annual_1x": -0.0468,
  "annual_2x": -0.094,
  "annual_3x": -0.1413,
  "cost_decay_rate": 1.0,
  "capacity_curve": {
    "5000000": {
      "annual": -0.06592822289640496,
      "sharpe": -0.18661057459758465,
      "maxdd": -0.9506105887181024
    },
    "50000000": {
      "annual": -0.08879555224791327,
      "sharpe": -0.2511928995476922,
      "maxdd": -0.9603043465227913
    },
    "500000000": {
      "annual": -0.10383025821014015,
      "sharpe": -0.29363875645481047,
      "maxdd": -0.9659676070041516
    },
    "2000000000": {
      "annual": -0.1050346663010309,
      "sharpe": -0.29704601417221016,
      "maxdd": -0.9664203535199848
    }
  },
  "capacity_limit_aum": 5000000
}
```

### Gate 7: Out-of-Sample & Stress Testing (❌ FAIL)
**Reasons/Warnings:**
- OOS Walk-Forward positive window ratio is below 50.0%: win_rate=41.7%
- Extreme regime dependency: Bear market return is severely negative: -162.95%

**Key Metrics:**
```json
{
  "wf_annual": -0.0247,
  "wf_sharpe": -0.0907,
  "wf_maxdd": -1.0,
  "wf_positive_ratio": 0.4167,
  "annual_delay_1d": -0.0424,
  "sharpe_delay_1d": -0.1264,
  "annual_delay_2d": -0.0224,
  "sharpe_delay_2d": -0.0685,
  "bull_annual": 1.0735,
  "bull_sharpe": 3.5593,
  "bear_annual": -1.6295,
  "bear_sharpe": -4.1302
}
```

### Gate 7A: Purged + Embargoed CV (❌ FAIL)
**Reasons/Warnings:**
- Purged + Embargoed CV Sharpe is too weak: observed=-0.09

**Key Metrics:**
```json
{
  "purge_window": 20,
  "embargo_window": 20,
  "forward_horizon": 20,
  "method": "rolling_origin_stability",
  "model_selection_cv": false,
  "cv_sharpe": -0.0907,
  "cv_annual": -0.0247,
  "cv_maxdd": -1.0,
  "cv_win_rate": 0.4167
}
```

### Gate 8: Live Monitoring (✅ PASS)
No errors or warnings detected.

**Key Metrics:**
```json
{
  "daily_mean_expected": -0.0002,
  "daily_vol_expected": 0.0223,
  "live_ic_se_20d": 0.2236,
  "live_ic_lower_limit": -0.1367,
  "monitoring_stop_loss_trigger": "performance falls below E[R] - 2 * std_dev * sqrt(days_live)",
  "max_live_drawdown_limit": -1.4125,
  "max_style_drift_tracking_error": 0.05,
  "max_sector_deviation": 0.15
}
```
