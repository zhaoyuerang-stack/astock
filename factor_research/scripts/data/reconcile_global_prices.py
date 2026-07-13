"""Reconcile a canonical global price panel against a second source."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_config.settings import get_settings  # noqa: E402
from lake.global_catalog import apply_source_admission, get_dataset_spec, get_source_spec  # noqa: E402
from lake.global_data import load_global_dataset  # noqa: E402
from lake.global_normalizers import normalize_global_frame  # noqa: E402
from lake.global_reconciliation import prepare_price_observations, reconcile_price_observations  # noqa: E402
from lake.global_validator import validate_global_frame  # noqa: E402
from scripts.data.update_global_data import _provider  # noqa: E402


def _price_column(dataset_id: str) -> str:
    if dataset_id in {"market_price_daily", "etf_daily"}:
        return "adjusted_close"
    if dataset_id in {"fx_daily", "commodity_daily"}:
        return "raw_close"
    raise ValueError(f"no reconciliation price column configured for {dataset_id}")


def _select_primary(
    dataset_id: str,
    *,
    source_id: str,
    start: str | None = None,
    end: str | None = None,
    symbols: set[str] | None = None,
    root: str | Path | None = None,
) -> object:
    frame = load_global_dataset(dataset_id, root=root)
    frame = frame.loc[frame["source_id"].astype(str) == source_id].copy()
    if start:
        frame = frame.loc[frame["session_date"] >= start]
    if end:
        frame = frame.loc[frame["session_date"] <= end]
    if symbols:
        frame = frame.loc[frame["symbol"].astype(str).isin(symbols)]
    if frame.empty:
        raise ValueError(f"no canonical rows found for {dataset_id} source={source_id}")
    return frame


def _fetch_secondary(
    dataset_id: str,
    *,
    source_id: str,
    start: str,
    end: str | None,
) -> object:
    settings = get_settings().global_data
    spec = get_dataset_spec(dataset_id)
    source = apply_source_admission(get_source_spec(source_id), settings.source_admissions.get(source_id))
    configured_key_env = settings.api_key_envs.get(source.provider, "")
    if configured_key_env:
        source = replace(source, api_key_env=configured_key_env)
    client = _provider(provider_mode=source.provider, api_key_envs=settings.api_key_envs, source=source)
    kwargs = {"start": start, "end": end}
    if source.provider == "openbb" and dataset_id in {"market_price_daily", "etf_daily"}:
        kwargs["adjustment_override"] = "splits_only"
    raw = client.fetch(spec, **kwargs)
    canonical = normalize_global_frame(raw, source=source, spec=spec, ingest_id="reconcile-review")
    validation = validate_global_frame(canonical, source=source, spec=spec)
    if validation.rejected:
        raise ValueError(f"secondary source validation rejected: {';'.join(validation.issues)}")
    if not validation.quarantine.empty:
        raise ValueError("secondary source returned quarantined rows during reconciliation")
    return validation.clean


def run_reconciliation(
    *,
    dataset_id: str = "market_price_daily",
    primary_source_id: str = "global_cboe_us_price_v1",
    secondary_source_id: str = "global_fmp_us_price_v1",
    start: str,
    end: str | None = None,
    symbols: list[str] | None = None,
    tolerance_bps: float = 5.0,
    severe_bps: float = 100.0,
    root: str | Path | None = None,
) -> dict:
    selected_symbols = {symbol.strip().upper() for symbol in (symbols or []) if symbol.strip()}
    primary = _select_primary(
        dataset_id,
        source_id=primary_source_id,
        start=start,
        end=end,
        symbols=selected_symbols or None,
        root=root,
    )
    secondary = _fetch_secondary(
        dataset_id,
        source_id=secondary_source_id,
        start=start,
        end=end,
    )
    if selected_symbols:
        secondary = secondary.loc[secondary["symbol"].astype(str).isin(selected_symbols)].copy()
    result = reconcile_price_observations(
        prepare_price_observations(primary, source_label=primary_source_id, price_column=_price_column(dataset_id)),
        prepare_price_observations(secondary, source_label=secondary_source_id, price_column=_price_column(dataset_id)),
        tolerance_bps=tolerance_bps,
        severe_bps=severe_bps,
    )
    return {
        "summary": result.summary,
        "symbols": result.symbol_summary.to_dict(orient="records"),
        "mismatches": result.mismatches.to_dict(orient="records"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="market_price_daily")
    parser.add_argument("--primary-source", default="global_cboe_us_price_v1")
    parser.add_argument("--secondary-source", default="global_fmp_us_price_v1")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end")
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--tolerance-bps", type=float, default=5.0)
    parser.add_argument("--severe-bps", type=float, default=100.0)
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    exit_code = 0
    try:
        report = run_reconciliation(
            dataset_id=args.dataset,
            primary_source_id=args.primary_source,
            secondary_source_id=args.secondary_source,
            start=args.start,
            end=args.end,
            symbols=args.symbol,
            tolerance_bps=args.tolerance_bps,
            severe_bps=args.severe_bps,
        )
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with audit-friendly output.
        exit_code = 1
        report = {
            "summary": {
                "ok": False,
                "dataset_id": args.dataset,
                "primary_source": args.primary_source,
                "secondary_source": args.secondary_source,
                "status": "reconciliation_failed",
                "error": f"{type(exc).__name__}: {exc}",
            },
            "symbols": [],
            "mismatches": [],
        }
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
