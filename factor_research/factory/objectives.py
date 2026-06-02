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


def _value(row, key):
    v = row.get(key)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return -np.inf if OBJECTIVE_DIRECTIONS[key] == "max" else np.inf
    return v


def dominates(a, b, keys=None):
    keys = keys or list(OBJECTIVE_DIRECTIONS)
    better_or_equal = True
    strictly_better = False
    for key in keys:
        av, bv = _value(a, key), _value(b, key)
        if OBJECTIVE_DIRECTIONS[key] == "max":
            if av < bv:
                better_or_equal = False
            if av > bv:
                strictly_better = True
        else:
            if av > bv:
                better_or_equal = False
            if av < bv:
                strictly_better = True
    return better_or_equal and strictly_better


def pareto_front(rows, keys=None):
    front = []
    for i, row in enumerate(rows):
        if not any(dominates(other, row, keys) for j, other in enumerate(rows) if i != j):
            front.append(row)
    return front


def scalar_rank(row):
    """Human-friendly sort for the first factory report."""
    corr_penalty = 0 if np.isnan(row["corr_to_baseline"]) else 0.05 * abs(row["corr_to_baseline"])
    return (
        row["annual"]
        + 0.10 * row["sharpe"]
        + row["maxdd"]
        - 0.02 * row["turnover_pa"]
        - row["cost_drag_pa"]
        - corr_penalty
    )
