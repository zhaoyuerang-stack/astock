"""Reconciliation helpers for multi-source global market data."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def _canonical_dates(values) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).tz_localize(None).normalize()


def prepare_price_observations(
    frame: pd.DataFrame,
    *,
    source_label: str,
    price_column: str,
    date_column: str = "session_date",
    symbol_column: str = "symbol",
) -> pd.DataFrame:
    required = {date_column, symbol_column, price_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise KeyError(f"missing columns for reconciliation: {','.join(missing)}")
    out = frame[[date_column, symbol_column, price_column]].copy()
    out["session_date"] = _canonical_dates(out[date_column])
    out["symbol"] = out[symbol_column].astype(str)
    out["close"] = pd.to_numeric(out[price_column], errors="coerce")
    out = out.dropna(subset=["session_date", "symbol", "close"])
    out = out.sort_values(["symbol", "session_date"]).drop_duplicates(["symbol", "session_date"], keep="last")
    out["source_label"] = source_label
    return out[["symbol", "session_date", "close", "source_label"]]


def _with_returns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values(["symbol", "session_date"]).copy()
    out["close_return"] = out.groupby("symbol", sort=False)["close"].pct_change()
    return out


@dataclass(frozen=True)
class PriceReconciliationResult:
    summary: dict
    symbol_summary: pd.DataFrame
    aligned: pd.DataFrame
    mismatches: pd.DataFrame


def reconcile_price_observations(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    *,
    tolerance_bps: float = 5.0,
    severe_bps: float = 100.0,
) -> PriceReconciliationResult:
    if tolerance_bps <= 0:
        raise ValueError("tolerance_bps must be positive")
    if severe_bps < tolerance_bps:
        raise ValueError("severe_bps must be >= tolerance_bps")

    left = _with_returns(primary)
    right = _with_returns(secondary)
    primary_label = str(left["source_label"].iloc[0]) if not left.empty else "primary"
    secondary_label = str(right["source_label"].iloc[0]) if not right.empty else "secondary"

    merged = left.merge(
        right,
        on=["symbol", "session_date"],
        how="outer",
        suffixes=("_primary", "_secondary"),
        indicator=True,
    ).sort_values(["symbol", "session_date"])

    merged["level_abs_diff_bps"] = (
        (merged["close_primary"] / merged["close_secondary"] - 1.0).abs() * 10000.0
    )
    merged.loc[
        merged["close_primary"].isna() | merged["close_secondary"].isna() | (merged["close_secondary"] == 0),
        "level_abs_diff_bps",
    ] = pd.NA
    merged["return_abs_diff_bps"] = (
        (merged["close_return_primary"] - merged["close_return_secondary"]).abs() * 10000.0
    )
    merged.loc[
        merged["close_return_primary"].isna() | merged["close_return_secondary"].isna(),
        "return_abs_diff_bps",
    ] = pd.NA

    classification = pd.Series("matched", index=merged.index, dtype="object")
    classification.loc[merged["_merge"] == "left_only"] = f"missing_in_{secondary_label}"
    classification.loc[merged["_merge"] == "right_only"] = f"missing_in_{primary_label}"

    both = merged["_merge"].eq("both")
    severe = both & (
        merged["level_abs_diff_bps"].fillna(0).gt(severe_bps)
        | merged["return_abs_diff_bps"].fillna(0).gt(severe_bps)
    )
    mild = both & ~severe & (
        merged["level_abs_diff_bps"].fillna(0).gt(tolerance_bps)
        | merged["return_abs_diff_bps"].fillna(0).gt(tolerance_bps)
    )
    classification.loc[severe] = "adjustment_or_unit_mismatch"
    classification.loc[mild] = "price_mismatch"
    merged["classification"] = classification

    mismatches = merged.loc[merged["classification"] != "matched"].copy()
    symbol_summary = (
        merged.groupby("symbol", dropna=False)
        .agg(
            aligned_rows=("classification", "size"),
            mismatch_rows=("classification", lambda x: int((x != "matched").sum())),
            max_level_abs_diff_bps=("level_abs_diff_bps", "max"),
            max_return_abs_diff_bps=("return_abs_diff_bps", "max"),
        )
        .reset_index()
        .sort_values(["mismatch_rows", "symbol"], ascending=[False, True])
    )

    summary = {
        "primary_source": primary_label,
        "secondary_source": secondary_label,
        "tolerance_bps": float(tolerance_bps),
        "severe_bps": float(severe_bps),
        "row_count_primary": int(len(left)),
        "row_count_secondary": int(len(right)),
        "aligned_rows": int(both.sum()),
        "primary_only_rows": int((merged["_merge"] == "left_only").sum()),
        "secondary_only_rows": int((merged["_merge"] == "right_only").sum()),
        "price_mismatch_rows": int((merged["classification"] == "price_mismatch").sum()),
        "adjustment_or_unit_mismatch_rows": int((merged["classification"] == "adjustment_or_unit_mismatch").sum()),
        "ok": bool(mismatches.empty),
    }
    return PriceReconciliationResult(
        summary=summary,
        symbol_summary=symbol_summary,
        aligned=merged,
        mismatches=mismatches,
    )
