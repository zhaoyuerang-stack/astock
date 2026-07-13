"""Source-schema to canonical-schema normalization for global data."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from pandas.api.types import is_bool

from lake.global_catalog import DatasetSpec, SourceSpec


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_column(frame: pd.DataFrame, column: str, *, dataset_id: str) -> None:
    if column not in frame.columns:
        raise ValueError(f"{dataset_id} requires {column}")


def _rename_if_missing(frame: pd.DataFrame, target: str, *aliases: str) -> None:
    if target in frame.columns:
        return
    for alias in aliases:
        if alias in frame.columns:
            frame.rename(columns={alias: target}, inplace=True)
            return


def _timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _append_common_columns(
    frame: pd.DataFrame,
    *,
    source: SourceSpec,
    spec: DatasetSpec,
    retrieved_at: str | None,
    ingest_id: str | None,
) -> pd.DataFrame:
    out = frame.copy()
    if "available_at" not in out.columns:
        raise ValueError(f"{spec.dataset_id} requires available_at")
    if not ingest_id:
        raise ValueError("ingest_id is required for canonical global data")
    out["source_id"] = source.source_id
    out["provider"] = source.provider
    out["dataset_id"] = spec.dataset_id
    # Assign a scalar timestamp so filtered source frames cannot misalign the
    # value by retaining a non-zero original index.
    out["retrieved_at"] = _timestamp(pd.Series([retrieved_at or _utc_now()])).iloc[0]
    out["ingest_id"] = ingest_id
    out["schema_version"] = source.canonical_schema_version
    out["source_timezone"] = source.timezone
    if "currency" not in out.columns:
        out["currency"] = source.currency
    out["available_at"] = _timestamp(out["available_at"])
    return out


def _normalize_macro(
    raw: pd.DataFrame,
    *,
    source: SourceSpec,
    spec: DatasetSpec,
    retrieved_at: str | None,
    ingest_id: str | None,
) -> pd.DataFrame:
    out = raw.copy()
    _rename_if_missing(out, "observation_date", "date")
    _rename_if_missing(out, "vintage_start", "realtime_start")
    _rename_if_missing(out, "vintage_end", "realtime_end")
    _rename_if_missing(out, "available_at", "release_at")
    for column in ("series_id", "observation_date", "value", "unit", "vintage_start", "vintage_end"):
        _require_column(out, column, dataset_id=spec.dataset_id)
    if "frequency" not in out.columns:
        out["frequency"] = spec.frequency
    out["observation_date"] = _timestamp(out["observation_date"])
    out["observed_at"] = out["observation_date"]
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    if source.provider == "alfred":
        # FRED/ALFRED emits "." for a non-observation (for example, a market
        # holiday). It is not a malformed zero or a value to forward-fill;
        # retain it in the immutable raw snapshot but omit it from canonical
        # observations so normal market closures do not consume quarantine.
        out = out.loc[out["value"].notna()].copy()
    # ALFRED uses a far-future vintage_end sentinel which exceeds pandas'
    # Timestamp bounds.  Retain ISO date strings for version comparisons.
    out["vintage_start"] = out["vintage_start"].astype(str)
    out["vintage_end"] = out["vintage_end"].astype(str)
    out = _append_common_columns(
        out,
        source=source,
        spec=spec,
        retrieved_at=retrieved_at,
        ingest_id=ingest_id,
    )
    out["date"] = out["observation_date"]
    if spec.date_column == "month":
        out["month"] = out["observation_date"].dt.strftime("%Y%m")
    return out


def _normalize_price(
    raw: pd.DataFrame,
    *,
    source: SourceSpec,
    spec: DatasetSpec,
    retrieved_at: str | None,
    ingest_id: str | None,
) -> pd.DataFrame:
    out = raw.copy()
    _rename_if_missing(out, "session_date", "date")
    if "available_at" not in out.columns and "session_close_at" in out.columns:
        out["available_at"] = out["session_close_at"]
    for column in (
        "symbol",
        "exchange",
        "session_date",
        "session_close_at",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "is_adjusted",
        "adjustment_version",
    ):
        _require_column(out, column, dataset_id=spec.dataset_id)
    out["session_date"] = _timestamp(out["session_date"])
    out["session_close_at"] = _timestamp(out["session_close_at"])
    out["observed_at"] = out["session_close_at"]
    for column in ("open", "high", "low", "close", "volume"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    if source.source_id == "global_cboe_us_price_v1":
        # CBOE historical O/H/L has source-level boundary inconsistencies on
        # a small but material subset of dates. Raw snapshots retain every
        # field for later reconciliation; canonical research data exposes
        # only the independently usable close/volume contract.
        out[["open", "high", "low"]] = pd.NA
        out["ohlc_quality"] = "close_only_unverified_ohlc"
    if source.source_id in {"alpha_vantage_commodity_spot_v1", "fred_commodity_spot_v1"}:
        out[["open", "high", "low"]] = pd.NA
        out["ohlc_quality"] = "close_only_spot_series"
    out = _append_common_columns(
        out,
        source=source,
        spec=spec,
        retrieved_at=retrieved_at,
        ingest_id=ingest_id,
    )
    if spec.dataset_id == "fx_daily":
        out["pair"] = out["symbol"].astype(str)
    # Pandas may materialize scalar bools as numpy.bool_.  Treat only actual
    # boolean values as adjustment flags; string truthy values stay invalid
    # for the validator rather than becoming silently adjusted prices.
    adjusted = out["is_adjusted"].map(lambda value: is_bool(value) and bool(value))
    if "raw_close" not in out.columns:
        out["raw_close"] = out["close"].where(~adjusted)
    if "adjusted_close" not in out.columns:
        out["adjusted_close"] = out["close"].where(adjusted)
    # Existing general price loaders use DatasetSpec.date_column (date), while
    # session_date remains the canonical market-specific field and primary key.
    out["date"] = out["session_date"]
    return out


def normalize_global_frame(
    raw: pd.DataFrame,
    *,
    source: SourceSpec,
    spec: DatasetSpec,
    retrieved_at: str | None = None,
    ingest_id: str | None = None,
) -> pd.DataFrame:
    """Normalize a source response without writing or silently filling PIT data."""
    if spec.dataset_id not in source.datasets:
        raise ValueError(f"{source.source_id} is not admitted for {spec.dataset_id}")
    if not isinstance(raw, pd.DataFrame):
        raise TypeError(f"raw global response must be a DataFrame, got {type(raw).__name__}")
    if spec.asset_class in {"macro", "rates"}:
        return _normalize_macro(
            raw,
            source=source,
            spec=spec,
            retrieved_at=retrieved_at,
            ingest_id=ingest_id,
        )
    if spec.dataset_id in {"market_price_daily", "etf_daily", "fx_daily", "commodity_daily"}:
        return _normalize_price(
            raw,
            source=source,
            spec=spec,
            retrieved_at=retrieved_at,
            ingest_id=ingest_id,
        )
    raise ValueError(f"no canonical normalizer is configured for {spec.dataset_id}")
