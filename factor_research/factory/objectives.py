"""Objective metrics and Pareto utilities."""
import numpy as np
import pandas as pd

from core.backtest import metrics


def max_drawdown(ret):
    if len(ret) == 0:
        return np.nan
    cum = (1 + ret).cumprod()
    return float((cum / cum.cummax() - 1).min())


def stability_score(yearly):
    if len(yearly) == 0:
        return np.nan
    return float(yearly.mean() / (yearly.std() + 1e-8))


def evaluate_objectives(ret, detail, benchmark_ret=None):
    m = metrics(ret)
    yearly = ret.groupby(ret.index.year).apply(lambda x: (1 + x).prod() - 1)
    oos = ret[ret.index >= pd.Timestamp("2023-01-01")]
    pressure = ret[ret.index < pd.Timestamp("2018-01-01")]
    corr = np.nan
    if benchmark_ret is not None:
        common = ret.index.intersection(benchmark_ret.index)
        if len(common) > 100:
            corr = float(ret.loc[common].corr(benchmark_ret.loc[common]))
    return {
        "annual": float(m["annual"]),
        "maxdd": float(m["maxdd"]),
        "sharpe": float(m["sharpe"]),
        "calmar": float(m["calmar"]),
        "turnover_pa": float(detail["turnover"].mean() * 252),
        "cost_drag_pa": float(detail["cost"].mean() * 252),
        "oos_annual": float(metrics(oos)["annual"]) if len(oos) >= 100 else np.nan,
        "pressure_maxdd": max_drawdown(pressure) if len(pressure) >= 100 else np.nan,
        "yearly_stability": stability_score(yearly),
        "corr_to_baseline": corr,
        "hit_single": bool(m["annual"] > 0.15 and abs(m["maxdd"]) < 0.20),
    }


# ---------------------------------------------------------------------------
# Phase-2: BacktestResult-based API
# ---------------------------------------------------------------------------

def evaluate_objectives_engine(result, benchmark=None):
    """Evaluate objectives from a ``BacktestResult`` (engine output).

    Parameters
    ----------
    result : BacktestResult
        Output of ``BacktestEngine.run()``.
    benchmark : BacktestResult, optional
        Baseline result for correlation calculation.

    Returns
    -------
    dict
        Same keys as ``evaluate_objectives()``.
    """
    ret = result.returns
    detail = result.detail
    m = result.metrics
    yearly = ret.groupby(ret.index.year).apply(lambda x: (1 + x).prod() - 1)
    oos = ret[ret.index >= pd.Timestamp("2023-01-01")]
    pressure = ret[ret.index < pd.Timestamp("2018-01-01")]

    corr = np.nan
    if benchmark is not None:
        common = ret.index.intersection(benchmark.returns.index)
        if len(common) > 100:
            corr = float(ret.loc[common].corr(benchmark.returns.loc[common]))

    return {
        "annual": float(m["annual"]),
        "maxdd": float(m["maxdd"]),
        "sharpe": float(m["sharpe"]),
        "calmar": float(m["calmar"]),
        "turnover_pa": float(detail["turnover"].mean() * 252),
        "cost_drag_pa": float(detail["cost"].mean() * 252),
        "oos_annual": float(metrics(oos)["annual"]) if len(oos) >= 100 else np.nan,
        "pressure_maxdd": max_drawdown(pressure) if len(pressure) >= 100 else np.nan,
        "yearly_stability": stability_score(yearly),
        "corr_to_baseline": corr,
        "hit_single": bool(m["annual"] > 0.15 and abs(m["maxdd"]) < 0.20),
    }


OBJECTIVE_DIRECTIONS = {
    "annual": "max",
    "maxdd": "max",          # less negative is better
    "sharpe": "max",
    "turnover_pa": "min",
    "cost_drag_pa": "min",
    "oos_annual": "max",
    "pressure_maxdd": "max",
    "corr_to_baseline": "min",
}

PARETO_KEYS = ["annual", "maxdd", "sharpe", "turnover_pa", "corr_to_baseline"]


def _value(row, key):
    v = row.get(key)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return -np.inf if OBJECTIVE_DIRECTIONS[key] == "max" else np.inf
    return v


def eligible_for_front(row):
    """Quality gate before Pareto marking.

    The factory can generate intentionally broad grids. Without a basic gate,
    weak rows may still become Pareto just because they are cheap, low-turnover
    or low-correlation. This keeps the front focused on plausible candidates.
    """
    annual = row.get("annual", np.nan)
    maxdd = row.get("maxdd", np.nan)
    sharpe = row.get("sharpe", np.nan)
    oos_annual = row.get("oos_annual", np.nan)
    if not all(np.isfinite(v) for v in [annual, maxdd, sharpe]):
        return False
    if annual <= 0 or sharpe <= 0 or maxdd <= -0.35:
        return False
    if np.isfinite(oos_annual) and oos_annual <= -0.05:
        return False
    return True


def dominates(a, b, keys=None, epsilon=1e-12):
    keys = keys or PARETO_KEYS
    better_or_equal = True
    strictly_better = False
    for key in keys:
        av, bv = _value(a, key), _value(b, key)
        if OBJECTIVE_DIRECTIONS[key] == "max":
            if av < bv - epsilon:
                better_or_equal = False
            if av > bv + epsilon:
                strictly_better = True
        else:
            if av > bv + epsilon:
                better_or_equal = False
            if av < bv - epsilon:
                strictly_better = True
    return better_or_equal and strictly_better


def pareto_front(rows, keys=None):
    candidates = [row for row in rows if eligible_for_front(row)]
    front = []
    for i, row in enumerate(candidates):
        if not any(dominates(other, row, keys) for j, other in enumerate(candidates) if i != j):
            front.append(row)
    return front


def scalar_rank(row):
    """Human-friendly sort for the first factory report."""
    corr = row.get("corr_to_baseline", np.nan)
    oos = row.get("oos_annual", np.nan)
    corr_penalty = 0 if np.isnan(corr) else 0.05 * abs(corr)
    oos_bonus = 0 if np.isnan(oos) else 0.25 * oos
    return (
        row["annual"]
        + oos_bonus
        + 0.10 * row["sharpe"]
        + row["maxdd"]
        - 0.02 * row["turnover_pa"]
        - row["cost_drag_pa"]
        - corr_penalty
    )
