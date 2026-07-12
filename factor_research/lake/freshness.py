"""Canonical price-lake freshness (single source of truth).

Both production readiness and scheduled daily update must use this module.
Never sample only the first N per-code parquet files — that can mis-report
freshness when those codes lag or lead the market.

Resolution order:
  1. ``data_lake/price/daily_all.parquet`` max(date) — compact authoritative table
  2. max(date) over **all** ``data_lake/price/daily/*.parquet`` — full scan fallback
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]


def actual_latest_price_date(root: Path | str | None = None) -> pd.Timestamp | None:
    """Return the latest trade date present in the price lake, or None if empty.

    Returns a timezone-naive ``pd.Timestamp`` at day resolution.
    """
    base = Path(root) if root is not None else _ROOT
    all_fp = base / "data_lake" / "price" / "daily_all.parquet"
    if all_fp.exists():
        ts = _max_date_from_parquet(all_fp)
        if ts is not None:
            return ts

    daily_dir = base / "data_lake" / "price" / "daily"
    if not daily_dir.exists():
        return None
    dates: list[pd.Timestamp] = []
    # Full scan — never [:N]. Partial scans caused readiness/ops divergence.
    for fp in daily_dir.glob("*.parquet"):
        ts = _max_date_from_parquet(fp)
        if ts is not None:
            dates.append(ts)
    return max(dates) if dates else None


def actual_latest_price_date_str(root: Path | str | None = None) -> str:
    """String form ``YYYY-MM-DD`` for readiness views; empty if unknown."""
    ts = actual_latest_price_date(root)
    if ts is None:
        return ""
    return str(pd.Timestamp(ts).date())


def _max_date_from_parquet(path: Path) -> pd.Timestamp | None:
    try:
        import pyarrow.compute as pc
        import pyarrow.parquet as pq

        column = pq.read_table(path, columns=["date"]).column(0)
        if len(column) == 0:
            return None
        value = pc.max(column).as_py()
        if value is None:
            return None
        return pd.Timestamp(value)
    except Exception:
        pass
    try:
        series = pd.read_parquet(path, columns=["date"])["date"]
        if len(series) == 0:
            return None
        return pd.Timestamp(pd.to_datetime(series).max())
    except Exception:
        return None
