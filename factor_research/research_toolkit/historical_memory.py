"""Conservative historical cross-section memory experiments.

The memory signal is deliberately simple: for each OOS date, compare the
shifted current cross-section against matured historical cross-sections, then
average the realized historical forward returns of the nearest neighbors.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RollingMemoryResult:
    windows: list[dict]
    summary: dict


def rank_ic_series(
    factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    *,
    min_names: int = 30,
) -> pd.Series:
    """Compute daily cross-sectional Spearman RankIC."""
    dates = factor.index.intersection(forward_ret.index)
    rows: dict[pd.Timestamp, float] = {}
    for dt in dates:
        f = factor.loc[dt].dropna()
        r = forward_ret.loc[dt].dropna()
        common = f.index.intersection(r.index)
        if len(common) < min_names:
            continue
        ic = f.loc[common].corr(r.loc[common], method="spearman")
        if pd.notna(ic):
            rows[pd.Timestamp(dt)] = float(ic)
    return pd.Series(rows).sort_index()


def _row_spearman(a: pd.Series, b: pd.Series, *, min_names: int) -> float | None:
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < min_names:
        return None
    corr = a.loc[common].corr(b.loc[common], method="spearman")
    return float(corr) if pd.notna(corr) else None


def _matured_history_positions(pos: int, horizon: int, lookback: int) -> range:
    # A label aligned at s is only known after s+horizon. At decision date t,
    # require s+horizon <= t-1, so today's signal cannot use immature labels.
    hi = pos - horizon - 1
    lo = max(0, hi - lookback + 1)
    if hi < lo:
        return range(0, 0)
    return range(lo, hi + 1)


def build_historical_memory_factor(
    factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    *,
    horizon: int = 20,
    lookback: int = 756,
    n_neighbors: int = 20,
    min_history: int = 20,
    min_names: int = 30,
) -> pd.DataFrame:
    """Build a memory factor from similar matured historical cross-sections.

    ``factor`` is shifted internally by one row. This enforces the experiment's
    T signal uses only T-1 factor information convention.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    if n_neighbors < 1:
        raise ValueError("n_neighbors must be >= 1")

    dates = factor.index.intersection(forward_ret.index)
    factor_s = factor.reindex(dates).shift(1)
    labels = forward_ret.reindex(index=dates, columns=factor.columns)
    out = pd.DataFrame(np.nan, index=dates, columns=factor.columns, dtype="float64")

    for pos, dt in enumerate(dates):
        current = factor_s.iloc[pos]
        if current.notna().sum() < min_names:
            continue

        scored: list[tuple[float, int]] = []
        for hpos in _matured_history_positions(pos, horizon, lookback):
            hist = factor_s.iloc[hpos]
            corr = _row_spearman(current, hist, min_names=min_names)
            if corr is not None and corr > 0:
                scored.append((corr, hpos))

        if len(scored) < min_history:
            continue

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_neighbors]
        weights = np.array([x[0] for x in top], dtype="float64")
        if not np.isfinite(weights).all() or weights.sum() <= 0:
            continue
        weights = weights / weights.sum()

        label_block = labels.iloc[[x[1] for x in top]].astype("float64")
        out.loc[dt] = label_block.mul(weights, axis=0).sum(axis=0, min_count=1)

    return out


def _rank_unit_matrix(frame: pd.DataFrame) -> np.ndarray:
    ranks = frame.rank(axis=1, method="average", na_option="keep").to_numpy(dtype="float64")
    valid = np.isfinite(ranks)
    counts = valid.sum(axis=1, keepdims=True)
    sums = np.where(valid, ranks, 0.0).sum(axis=1, keepdims=True)
    means = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
    centered = np.where(valid, ranks - means, 0.0)
    norms = np.sqrt((centered * centered).sum(axis=1, keepdims=True))
    return np.divide(centered, norms, out=np.zeros_like(centered), where=norms > 0)


def build_historical_memory_factor_fast(
    factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    *,
    horizon: int = 20,
    lookback: int = 756,
    n_neighbors: int = 20,
    min_history: int = 20,
    min_names: int = 30,
) -> pd.DataFrame:
    """Vectorized memory factor for full-universe grid experiments.

    The time discipline is identical to ``build_historical_memory_factor``:
    the factor is shifted by one row internally and only matured labels are
    eligible. Similarity is computed from full-row rank unit vectors so the
    no-missing-data case matches Spearman correlation exactly.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    if n_neighbors < 1:
        raise ValueError("n_neighbors must be >= 1")

    dates = factor.index.intersection(forward_ret.index)
    factor_s = factor.reindex(dates).shift(1)
    labels = forward_ret.reindex(index=dates, columns=factor.columns).astype("float64")
    rank_units = _rank_unit_matrix(factor_s)
    label_arr = labels.to_numpy(dtype="float64")
    out = np.full(label_arr.shape, np.nan, dtype="float64")

    valid_names = factor_s.notna().sum(axis=1).to_numpy()
    for pos in range(len(dates)):
        if valid_names[pos] < min_names:
            continue
        hpos = list(_matured_history_positions(pos, horizon, lookback))
        if len(hpos) < min_history:
            continue

        sims = rank_units[hpos] @ rank_units[pos]
        sims = np.where(np.isfinite(sims) & (sims > 0), sims, np.nan)
        ok = np.isfinite(sims)
        if int(ok.sum()) < min_history:
            continue

        ok_idx = np.flatnonzero(ok)
        if len(ok_idx) > n_neighbors:
            best_local = ok_idx[np.argpartition(sims[ok_idx], -n_neighbors)[-n_neighbors:]]
            best_local = best_local[np.argsort(sims[best_local])[::-1]]
        else:
            best_local = ok_idx[np.argsort(sims[ok_idx])[::-1]]

        weights = sims[best_local].astype("float64")
        if not np.isfinite(weights).all() or weights.sum() <= 0:
            continue
        weights = weights / weights.sum()
        rows = label_arr[np.asarray(hpos, dtype=int)[best_local]]
        weighted = np.nansum(rows * weights[:, None], axis=0)
        has_value = np.isfinite(rows).any(axis=0)
        weighted[~has_value] = np.nan
        out[pos] = weighted

    return pd.DataFrame(out, index=dates, columns=factor.columns)


def rolling_memory_rankic(
    factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    *,
    horizon: int = 20,
    lookback: int = 756,
    n_neighbors: int = 20,
    train_days: int = 756,
    test_days: int = 252,
    step_days: int | None = None,
    min_history: int = 20,
    min_names: int = 30,
) -> RollingMemoryResult:
    """Compare shifted base factor vs memory factor across rolling OOS windows."""
    dates = factor.index.intersection(forward_ret.index)
    if step_days is None:
        step_days = test_days
    memory = build_historical_memory_factor_fast(
        factor.reindex(dates),
        forward_ret.reindex(dates),
        horizon=horizon,
        lookback=lookback,
        n_neighbors=n_neighbors,
        min_history=min_history,
        min_names=min_names,
    )
    base_ic = rank_ic_series(factor.reindex(dates).shift(1), forward_ret.reindex(dates), min_names=min_names)
    memory_ic = rank_ic_series(memory, forward_ret.reindex(dates), min_names=min_names)

    windows: list[dict] = []
    start_pos = max(train_days, horizon + min_history + 1)
    for pos in range(start_pos, max(start_pos, len(dates) - test_days + 1), step_days):
        wdates = dates[pos: pos + test_days]
        if len(wdates) == 0:
            continue
        b = base_ic.reindex(wdates).dropna()
        m = memory_ic.reindex(wdates).dropna()
        if len(b) == 0 or len(m) == 0:
            continue
        windows.append({
            "start": str(wdates[0].date()),
            "end": str(wdates[-1].date()),
            "base_rankic": float(b.mean()),
            "memory_rankic": float(m.mean()),
            "rankic_delta": float(m.mean() - b.mean()),
            "base_count": int(len(b)),
            "memory_count": int(len(m)),
        })

    base_vals = [w["base_rankic"] for w in windows]
    memory_vals = [w["memory_rankic"] for w in windows]
    delta_vals = [w["rankic_delta"] for w in windows]
    summary = {
        "method": "historical_similar_cross_section_memory",
        "horizon": int(horizon),
        "lookback": int(lookback),
        "n_neighbors": int(n_neighbors),
        "windows": int(len(windows)),
        "base_rankic": float(np.mean(base_vals)) if base_vals else float("nan"),
        "memory_rankic": float(np.mean(memory_vals)) if memory_vals else float("nan"),
        "rankic_delta": float(np.mean(delta_vals)) if delta_vals else float("nan"),
        "positive_delta_ratio": float(np.mean([d > 0 for d in delta_vals])) if delta_vals else float("nan"),
    }
    return RollingMemoryResult(windows=windows, summary=summary)
