"""Quality gates for normalized global data."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from pandas.api.types import is_bool

from lake.global_catalog import DatasetSpec, SourceSpec


COMMON_COLUMNS = (
    "source_id",
    "provider",
    "dataset_id",
    "observed_at",
    "available_at",
    "retrieved_at",
    "ingest_id",
    "schema_version",
    "source_timezone",
    "currency",
)


@dataclass(frozen=True)
class GlobalValidationResult:
    clean: pd.DataFrame
    quarantine: pd.DataFrame
    issues: tuple[str, ...]
    rejected: bool

    @property
    def status(self) -> str:
        if self.rejected:
            return "rejected"
        if len(self.quarantine):
            return "partial_ok"
        return "available"


def _dataset_columns(spec: DatasetSpec) -> tuple[str, ...]:
    if spec.dataset_id in {"macro_daily", "macro_monthly", "rates_daily"}:
        return ("series_id", "observation_date", "value", "unit", "frequency", "vintage_start", "vintage_end")
    if spec.dataset_id in {"market_price_daily", "etf_daily", "fx_daily", "commodity_daily"}:
        return (
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
        )
    raise ValueError(f"no validation schema is configured for {spec.dataset_id}")


def primary_key_for_dataset(spec: DatasetSpec) -> tuple[str, ...]:
    if spec.dataset_id in {"macro_daily", "macro_monthly", "rates_daily"}:
        return ("series_id", "observation_date", "vintage_start")
    if spec.dataset_id in {"market_price_daily", "etf_daily", "fx_daily", "commodity_daily"}:
        return ("symbol", "exchange", "session_date", "adjustment_version")
    raise ValueError(f"no primary-key policy is configured for {spec.dataset_id}")


def _empty_like(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.iloc[0:0].copy()
    out["_reason"] = pd.Series(dtype="object")
    return out


def _append_reason(reasons: pd.Series, mask: pd.Series, reason: str) -> None:
    reasons.loc[mask] = reasons.loc[mask].map(lambda value: f"{value};{reason}" if value else reason)


def _reject(frame: pd.DataFrame, issue: str) -> GlobalValidationResult:
    return GlobalValidationResult(
        clean=frame.iloc[0:0].copy(),
        quarantine=_empty_like(frame),
        issues=(issue,),
        rejected=True,
    )


def validate_global_frame(
    frame: pd.DataFrame,
    *,
    source: SourceSpec,
    spec: DatasetSpec,
) -> GlobalValidationResult:
    """Validate canonical data and isolate row-level errors before lake writes."""
    required = COMMON_COLUMNS + _dataset_columns(spec)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        return _reject(frame, f"missing canonical columns: {','.join(missing)}")
    if frame.empty:
        return _reject(frame, "empty canonical batch")

    out = frame.copy()
    if not out["source_id"].eq(source.source_id).all():
        return _reject(frame, "source_id does not match source admission")
    if not out["dataset_id"].eq(spec.dataset_id).all():
        return _reject(frame, "dataset_id does not match dataset spec")

    for column in ("observed_at", "available_at", "retrieved_at"):
        out[column] = pd.to_datetime(out[column], errors="coerce", utc=True)

    key = primary_key_for_dataset(spec)
    conflict_groups = []
    for _, group in out.groupby(list(key), dropna=False, sort=False):
        if len(group) <= 1:
            continue
        if len(group.drop(columns=[], errors="ignore").drop_duplicates()) > 1:
            conflict_groups.append(group.index)
    if conflict_groups:
        return _reject(frame, "primary key conflict")

    reasons = pd.Series("", index=out.index, dtype="object")
    for column in required:
        null = out[column].isna()
        if out[column].dtype == object:
            null = null | out[column].astype(str).str.strip().eq("")
        _append_reason(reasons, null, f"missing_{column}")
    _append_reason(reasons, out["available_at"] < out["observed_at"], "available_before_observed")
    _append_reason(reasons, out["retrieved_at"] < out["available_at"], "available_after_retrieved")

    if spec.dataset_id in {"macro_daily", "macro_monthly", "rates_daily"}:
        observation = pd.to_datetime(out["observation_date"], errors="coerce", utc=True)
        _append_reason(reasons, observation.isna(), "invalid_observation_date")
        _append_reason(reasons, out["value"].isna(), "invalid_value")
        _append_reason(reasons, out["vintage_start"].astype(str) > out["vintage_end"].astype(str), "invalid_vintage_range")

    if spec.dataset_id in {"market_price_daily", "etf_daily", "fx_daily", "commodity_daily"}:
        for column in ("open", "high", "low", "close", "volume"):
            _append_reason(reasons, out[column].isna(), f"invalid_{column}")
        _append_reason(reasons, (out[["open", "high", "low", "close"]] <= 0).any(axis=1), "non_positive_price")
        _append_reason(reasons, out["volume"] < 0, "negative_volume")
        # CBOE historical OHLC values are rounded independently to cents, so
        # a valid bar can cross an OHLC boundary by a few cents. Keep this
        # source-specific price precision allowance small and explicit.
        price_tolerance = 0.05 if source.source_id == "global_cboe_us_price_v1" else 0.0
        lower = out["low"] > (out[["open", "close"]].min(axis=1) + price_tolerance)
        upper = out["high"] < (out[["open", "close"]].max(axis=1) - price_tolerance)
        _append_reason(reasons, lower | upper, "ohlc_inconsistent")
        _append_reason(reasons, ~out["is_adjusted"].map(is_bool), "invalid_is_adjusted")
        if "raw_close" not in out.columns or "adjusted_close" not in out.columns:
            return _reject(frame, "price adjustment fields are not separated")
        _append_reason(reasons, (~out["is_adjusted"]) & out["raw_close"].isna(), "missing_raw_close")
        _append_reason(reasons, out["is_adjusted"] & out["adjusted_close"].isna(), "missing_adjusted_close")

    quarantine = out.loc[reasons.ne("")].copy()
    quarantine["_reason"] = reasons.loc[quarantine.index]
    clean = out.loc[reasons.eq("")].drop_duplicates(subset=list(key), keep="last").copy()
    ratio = len(quarantine) / len(out)
    if ratio > source.max_quarantine_ratio:
        return GlobalValidationResult(
            clean=out.iloc[0:0].copy(),
            quarantine=quarantine,
            issues=(f"quarantine ratio {ratio:.2%} exceeds {source.max_quarantine_ratio:.2%}",),
            rejected=True,
        )
    return GlobalValidationResult(
        clean=clean,
        quarantine=quarantine,
        issues=(),
        rejected=False,
    )
