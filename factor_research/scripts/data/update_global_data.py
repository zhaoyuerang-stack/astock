"""Update or probe the optional global multi-asset data layer."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_config.settings import GlobalDataConfig, get_settings  # noqa: E402
from lake.global_catalog import (  # noqa: E402
    SourceSpec,
    apply_source_admission,
    get_sources_for_dataset,
    get_dataset_spec,
    get_source_for_dataset,
)
from lake.global_normalizers import normalize_global_frame  # noqa: E402
from lake.global_validator import validate_global_frame  # noqa: E402
from lake.global_writer import (  # noqa: E402
    frame_content_hash,
    read_global_manifest,
    read_global_raw_snapshot,
    record_global_dataset_status,
    write_global_quarantine,
    write_global_raw_snapshot,
    write_validated_global_dataset,
)
from lake.sources.openbb_global import OpenBBGlobalProvider  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _settings() -> GlobalDataConfig:
    return get_settings().global_data


def _provider(
    provider=None,
    provider_mode: str = "openbb",
    api_key_envs: dict[str, str] | None = None,
    source: SourceSpec | None = None,
):
    if provider is not None:
        return provider
    if provider_mode == "openbb":
        # Settings contains credentials for several providers (for example
        # ALFRED/FRED). OpenBB must check only the selected source's own
        # entitlement, otherwise an unrelated missing key blocks yfinance.
        source_keys = {"source": source.api_key_env} if source and source.api_key_env else {}
        return OpenBBGlobalProvider(api_key_envs=source_keys, source=source)
    if provider_mode == "alfred":
        if source is None:
            raise ValueError("alfred provider requires a source admission record")
        from lake.sources.alfred_macro import AlfredMacroProvider

        return AlfredMacroProvider(source=source)
    raise ValueError(f"unsupported global data provider_mode: {provider_mode}")


def _select_dataset_ids(
    dataset_ids: Iterable[str] | None,
    *,
    settings: GlobalDataConfig,
    all_enabled: bool = False,
) -> list[str]:
    ids = [str(x) for x in (dataset_ids or []) if str(x)]
    if ids:
        return ids
    if all_enabled:
        return list(settings.datasets) if settings.enabled else []
    if settings.enabled:
        return list(settings.datasets or ())
    return []


def _incremental_start(root: str | Path | None, dataset_id: str, requested_start: str | None) -> str | None:
    if requested_start:
        return requested_start
    watermark = (read_global_manifest(root).get("datasets", {}).get(dataset_id, {}) or {}).get("watermark", "")
    if not watermark:
        return None
    try:
        last_available = datetime.fromisoformat(str(watermark).replace("Z", "+00:00")).date()
    except ValueError:
        return None
    # Revisions and late source corrections are common; do not fetch only the
    # exact last watermark date and then miss a corrected prior observation.
    return (last_available - timedelta(days=5)).isoformat()


def run_global_update(
    *,
    root: str | Path | None = None,
    dataset_ids: Iterable[str] | None = None,
    provider=None,
    source: SourceSpec | None = None,
    source_id: str | None = None,
    provider_mode: str | None = None,
    all_enabled: bool = False,
    dry_run: bool = False,
    probe: bool = False,
    from_watermark: bool = False,
    replay_ingest: str = "",
    validate_only: bool = False,
    quarantine_report: bool = False,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    settings = _settings()
    mode = provider_mode or (source.provider if source else settings.provider_mode)
    required = bool(settings.required)
    selected = _select_dataset_ids(dataset_ids, settings=settings, all_enabled=all_enabled)
    result = {
        "ok": True,
        "required": required,
        "skipped": False,
        "provider_mode": mode,
        "started_at": _now(),
        "finished_at": "",
        "quarantine_report": bool(quarantine_report),
        "detail": {},
    }
    if not selected:
        result.update({"skipped": True, "reason": "global_data_disabled_or_no_datasets", "finished_at": _now()})
        return result

    clients = {}
    failures = 0
    for dataset_id in selected:
        spec = get_dataset_spec(dataset_id)
        request_start = _incremental_start(root, dataset_id, start) if from_watermark else start
        try:
            if source is not None:
                dataset_source = source
            elif source_id:
                dataset_source = get_source_for_dataset(dataset_id, source_id=source_id)
                dataset_source = apply_source_admission(
                    dataset_source,
                    settings.source_admissions.get(dataset_source.source_id),
                )
            else:
                candidates = [
                    apply_source_admission(item, settings.source_admissions.get(item.source_id))
                    for item in get_sources_for_dataset(dataset_id)
                ]
                dataset_source = next((item for item in candidates if item.enabled), candidates[0])
            configured_key_env = settings.api_key_envs.get(dataset_source.provider, "")
            if configured_key_env:
                dataset_source = replace(dataset_source, api_key_env=configured_key_env)
        except (KeyError, ValueError) as exc:
            failures += 1
            result["detail"][dataset_id] = {
                "ok": False,
                "dataset_id": dataset_id,
                "status": "source_not_admitted",
                "required": required or spec.required,
                "error": str(exc),
            }
            continue
        if not dataset_source.enabled:
            failures += 1
            detail = {
                "ok": False,
                "source_id": dataset_source.source_id,
                "provider": dataset_source.provider,
                "dataset_id": dataset_id,
                "status": "source_not_admitted",
                "required": required or spec.required,
                "error": f"admission={dataset_source.admission_status}; license={dataset_source.license_status}",
            }
            result["detail"][dataset_id] = detail
            if not dry_run:
                record_global_dataset_status(
                    spec,
                    root=root,
                    source=dataset_source,
                    status=detail["status"],
                    last_error=detail["error"],
                )
            continue
        if provider_mode and provider_mode != dataset_source.provider:
            failures += 1
            detail = {
                "ok": False,
                "source_id": dataset_source.source_id,
                "provider": dataset_source.provider,
                "dataset_id": dataset_id,
                "status": "provider_mode_mismatch",
                "required": required or spec.required,
                "error": f"source requires provider_mode={dataset_source.provider}, got {provider_mode}",
            }
            result["detail"][dataset_id] = detail
            if not dry_run:
                record_global_dataset_status(
                    spec,
                    root=root,
                    source=dataset_source,
                    status=detail["status"],
                    last_error=detail["error"],
                )
            continue
        client = None
        if replay_ingest and not (probe or dry_run):
            status = {
                "ok": True,
                "source_id": dataset_source.source_id,
                "provider": dataset_source.provider,
                "dataset_id": dataset_id,
                "status": "replay_available",
            }
        else:
            client = clients.get(dataset_source.source_id)
            if client is None:
                client = _provider(
                    provider=provider,
                    provider_mode=provider_mode or dataset_source.provider,
                    api_key_envs=settings.api_key_envs,
                    source=dataset_source,
                )
                clients[dataset_source.source_id] = client
            status = client.probe(spec)
        if probe or dry_run:
            detail = {
                **status,
                "required": required or spec.required,
                "dry_run": dry_run,
                "probe_only": probe,
            }
            result["detail"][dataset_id] = detail
            if not status.get("ok"):
                failures += 1
                if not dry_run:
                    record_global_dataset_status(
                        spec,
                        root=root,
                        source=dataset_source,
                        status=str(status.get("status") or "failed"),
                        last_error=str(status.get("error") or ""),
                    )
            continue

        if not status.get("ok"):
            failures += 1
            detail = {
                **status,
                "required": required or spec.required,
                "ok": False,
            }
            result["detail"][dataset_id] = detail
            record_global_dataset_status(
                spec,
                root=root,
                source=dataset_source,
                status=str(status.get("status") or "failed"),
                last_error=str(status.get("error") or ""),
            )
            continue

        try:
            if replay_ingest:
                raw, metadata = read_global_raw_snapshot(
                    source=dataset_source,
                    spec=spec,
                    ingest_id=replay_ingest,
                    root=root,
                )
                raw_snapshot = {
                    "ingest_id": replay_ingest,
                    "retrieved_at": metadata.get("retrieved_at", _now()),
                    "content_hash": metadata.get("content_hash", ""),
                }
            else:
                raw = client.fetch(spec, start=request_start, end=end)
                if not isinstance(raw, pd.DataFrame):
                    raise TypeError(f"provider returned {type(raw).__name__}, expected DataFrame")
                if validate_only:
                    content_hash = frame_content_hash(raw)
                    raw_snapshot = {
                        "ingest_id": f"validate-{dataset_source.source_id}-{content_hash[:16]}",
                        "retrieved_at": _now(),
                        "content_hash": content_hash,
                    }
                else:
                    raw_snapshot = write_global_raw_snapshot(raw, source=dataset_source, spec=spec, root=root)
            canonical = normalize_global_frame(
                raw,
                source=dataset_source,
                spec=spec,
                retrieved_at=raw_snapshot["retrieved_at"],
                ingest_id=raw_snapshot["ingest_id"],
            )
            validation = validate_global_frame(canonical, source=dataset_source, spec=spec)
            if validation.rejected:
                quarantine = {"count": int(len(validation.quarantine))}
                if not validate_only:
                    quarantine = write_global_quarantine(
                        validation.quarantine,
                        source=dataset_source,
                        spec=spec,
                        ingest_id=raw_snapshot["ingest_id"],
                        root=root,
                    )
                message = "; ".join(validation.issues)
                result["detail"][dataset_id] = {
                    "ok": False,
                    "source_id": dataset_source.source_id,
                    "provider": dataset_source.provider,
                    "dataset_id": dataset_id,
                    "status": "validation_rejected",
                    "required": required or spec.required,
                    "error": message,
                    "quarantine_count": quarantine["count"],
                    "replayed": bool(replay_ingest),
                }
                if not validate_only:
                    record_global_dataset_status(
                        spec,
                        root=root,
                        source=dataset_source,
                        status="validation_rejected",
                        last_error=message,
                    )
                failures += 1
                continue
            if validate_only:
                result["detail"][dataset_id] = {
                    "ok": True,
                    "source_id": dataset_source.source_id,
                    "provider": dataset_source.provider,
                    "dataset_id": dataset_id,
                    "status": validation.status,
                    "required": required or spec.required,
                    "validate_only": True,
                    "replayed": bool(replay_ingest),
                    "row_count": int(len(validation.clean)),
                    "quarantine_count": int(len(validation.quarantine)),
                    "raw_hash": raw_snapshot["content_hash"],
                }
                continue
            write_result = write_validated_global_dataset(
                validation,
                source=dataset_source,
                spec=spec,
                ingest_id=raw_snapshot["ingest_id"],
                root=root,
                raw_snapshot=raw_snapshot,
            )
            result["detail"][dataset_id] = {
                **write_result,
                "source_id": dataset_source.source_id,
                "required": required or spec.required,
                "replayed": bool(replay_ingest),
            }
        except Exception as exc:  # noqa: BLE001 - surfaced in manifest and scheduler report.
            failures += 1
            message = f"{type(exc).__name__}: {exc}"
            result["detail"][dataset_id] = {
                "ok": False,
                "provider": spec.provider,
                "source_id": dataset_source.source_id,
                "dataset_id": spec.dataset_id,
                "status": "fetch_failed",
                "required": required or spec.required,
                "error": message,
            }
            record_global_dataset_status(
                spec,
                root=root,
                source=dataset_source,
                status="fetch_failed",
                last_error=message,
            )

    result["ok"] = failures == 0
    result["failure_count"] = failures
    result["finished_at"] = _now()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", action="append", default=[], help="Dataset id to update/probe.")
    parser.add_argument("--all-enabled", action="store_true", help="Use enabled datasets declared in settings.")
    parser.add_argument("--probe", action="store_true", help="Probe provider availability without fetching data.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write dataset parquet files.")
    parser.add_argument("--provider-mode", default=None, help="Provider mode, default from settings.")
    parser.add_argument("--source", default=None, help="Source admission id to use for every selected dataset.")
    parser.add_argument("--from-watermark", action="store_true", help="Use the dataset manifest watermark as fetch start when available.")
    parser.add_argument("--replay-ingest", default="", help="Replay an immutable raw ingest id instead of fetching a provider.")
    parser.add_argument("--validate-only", action="store_true", help="Normalize and validate without writing canonical data or manifest status.")
    parser.add_argument("--quarantine-report", action="store_true", help="Include quarantine counts/paths in the JSON result.")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    args = parser.parse_args(argv)
    result = run_global_update(
        root=ROOT,
        dataset_ids=args.dataset,
        provider_mode=args.provider_mode,
        source_id=args.source,
        all_enabled=args.all_enabled,
        dry_run=args.dry_run,
        probe=args.probe,
        from_watermark=args.from_watermark,
        replay_ingest=args.replay_ingest,
        validate_only=args.validate_only,
        quarantine_report=args.quarantine_report,
        start=args.start,
        end=args.end,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") or not result.get("required") else 1


if __name__ == "__main__":
    raise SystemExit(main())
