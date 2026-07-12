"""Read APIs for the optional global multi-asset lake namespace."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from lake.global_catalog import get_dataset_spec
from lake.global_writer import global_dataset_path
def _canonical_date_index(values) -> pd.DatetimeIndex:
    """Return date-only, timezone-naive indices compatible with lake loaders."""
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).tz_localize(None)


def load_global_dataset(dataset_id: str, *, root: str | Path | None = None) -> pd.DataFrame:
    spec = get_dataset_spec(dataset_id)
    path = global_dataset_path(spec, root)
    if not path.exists():
        raise FileNotFoundError(f"global dataset not found: {dataset_id} ({path})")
    return pd.read_parquet(path)


def load_global_series(
    dataset_id: str,
    *,
    root: str | Path | None = None,
    field: str = "value",
    symbol: str = "",
) -> pd.Series:
    spec = get_dataset_spec(dataset_id)
    frame = load_global_dataset(dataset_id, root=root)
    if symbol and spec.symbol_column and spec.symbol_column in frame.columns:
        frame = frame[frame[spec.symbol_column].astype(str) == symbol]
    if field not in frame.columns:
        raise KeyError(f"{field} not found in {dataset_id}")
    if spec.date_column not in frame.columns:
        raise KeyError(f"{spec.date_column} not found in {dataset_id}")
    idx = _canonical_date_index(frame[spec.date_column])
    series = pd.Series(frame[field].to_numpy(), index=idx, name=symbol or dataset_id)
    return series.sort_index()


def load_global_price_panel(
    dataset_id: str,
    *,
    root: str | Path | None = None,
    field: str = "close",
    adjustment_basis: str = "",
) -> pd.DataFrame:
    spec = get_dataset_spec(dataset_id)
    frame = load_global_dataset(dataset_id, root=root)
    if adjustment_basis not in {"raw", "adjusted"}:
        raise ValueError("adjustment_basis must be raw or adjusted")
    price_field = f"{adjustment_basis}_{field}"
    if not spec.symbol_column:
        raise ValueError(f"{dataset_id} does not declare a symbol column")
    for col in (spec.date_column, spec.symbol_column, price_field):
        if col not in frame.columns:
            raise KeyError(f"{col} not found in {dataset_id}")
    if frame[price_field].notna().sum() == 0:
        raise ValueError(f"{dataset_id} does not provide {adjustment_basis} prices")
    pivot = frame.pivot_table(
        index=_canonical_date_index(frame[spec.date_column]),
        columns=spec.symbol_column,
        values=price_field,
        aggfunc="last",
    )
    pivot.index.name = None
    return pivot.sort_index().sort_index(axis=1)


def align_global_macro(
    frame: pd.DataFrame,
    trade_dates,
    *,
    dataset_id: str = "macro_daily",
    fields: list[str] | None = None,
    series_id: str = "",
    as_of_date=None,
) -> pd.DataFrame:
    spec = get_dataset_spec(dataset_id)
    if "available_at" not in frame.columns:
        raise ValueError(f"{dataset_id} is missing available_at; PIT alignment is unavailable")
    if as_of_date is None:
        raise ValueError("as_of_date is required for global macro PIT alignment")
    dates = _canonical_date_index(trade_dates)
    if isinstance(as_of_date, str):
        offset = pd.to_timedelta(as_of_date.rstrip("Z"))
        as_of = dates.tz_localize("UTC") + offset
    else:
        as_of = pd.DatetimeIndex(pd.to_datetime(as_of_date, utc=True))
        if len(as_of) != len(dates):
            raise ValueError("as_of_date sequence must match trade_dates")

    data = frame.copy()
    data["available_at"] = pd.to_datetime(data["available_at"], errors="coerce", utc=True)
    if data["available_at"].isna().any():
        raise ValueError(f"{dataset_id} contains invalid available_at")
    if "series_id" in data.columns:
        if series_id:
            data = data[data["series_id"].astype(str) == series_id]
        elif data["series_id"].nunique(dropna=True) > 1:
            raise ValueError(f"{dataset_id} contains multiple series; series_id is required")
    if data.empty:
        raise ValueError(f"{dataset_id} has no rows for series_id={series_id}")
    if fields:
        keep = ["available_at"] + [field for field in fields if field in data.columns]
        data = data[keep]
    requested = pd.DataFrame({"trade_date": dates, "as_of": as_of}).sort_values("as_of")
    out = pd.DataFrame(index=dates)
    for field in [column for column in data.columns if column != "available_at"]:
        observations = data[["available_at", field]].dropna(subset=[field]).sort_values("available_at")
        aligned = pd.merge_asof(
            requested,
            observations,
            left_on="as_of",
            right_on="available_at",
            direction="backward",
        )
        out[field] = aligned.set_index("trade_date")[field].reindex(dates)
    return out


def load_global_macro(
    dataset_id: str,
    trade_dates,
    *,
    root: str | Path | None = None,
    fields: list[str] | None = None,
    series_id: str = "",
    as_of_date=None,
) -> pd.DataFrame:
    frame = load_global_dataset(dataset_id, root=root)
    return align_global_macro(
        frame,
        trade_dates,
        dataset_id=dataset_id,
        fields=fields,
        series_id=series_id,
        as_of_date=as_of_date,
    )
