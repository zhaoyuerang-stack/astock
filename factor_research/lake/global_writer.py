"""Canonical writer for the optional global data lake namespace."""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from lake.global_catalog import DatasetSpec, SourceSpec
from lake.global_validator import GlobalValidationResult, primary_key_for_dataset


def _root(root: str | Path | None = None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parents[1]


def global_base_path(root: str | Path | None = None) -> Path:
    return _root(root) / "data_lake" / "global"


def global_raw_base_path(root: str | Path | None = None) -> Path:
    return _root(root) / "data_lake" / "global_raw"


def global_quarantine_base_path(root: str | Path | None = None) -> Path:
    return _root(root) / "data_lake" / "global_quarantine"


def global_manifest_path(root: str | Path | None = None) -> Path:
    return _root(root) / "data_lake" / "global_manifest.json"


def global_dataset_path(spec: DatasetSpec, root: str | Path | None = None) -> Path:
    return global_base_path(root) / f"{spec.storage_key}.parquet"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def frame_content_hash(frame: pd.DataFrame) -> str:
    """Stable content hash used to bind a canonical batch to its raw snapshot."""
    payload = {
        "columns": [str(column) for column in frame.columns],
        "dtypes": [str(dtype) for dtype in frame.dtypes],
        "data": frame.to_json(orient="split", date_format="iso", date_unit="ns", default_handler=str),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _redact_request_summary(value: Any, *, key: str = "") -> Any:
    sensitive = ("token", "key", "secret", "password", "authorization", "cookie")
    if any(marker in key.lower() for marker in sensitive):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k): _redact_request_summary(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_request_summary(item, key=key) for item in value]
    return value


def write_global_raw_snapshot(
    frame: pd.DataFrame,
    *,
    source: SourceSpec,
    spec: DatasetSpec,
    root: str | Path | None = None,
    request_summary: dict[str, Any] | None = None,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Persist an immutable raw provider response before normalization."""
    if spec.dataset_id not in source.datasets:
        raise ValueError(f"{source.source_id} is not admitted for {spec.dataset_id}")
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"raw snapshot must be a DataFrame, got {type(frame).__name__}")
    content_hash = frame_content_hash(frame)
    ingest_id = f"{source.source_id}-{spec.dataset_id}-{content_hash[:16]}"
    snapshot_dir = global_raw_base_path(root) / source.source_id / spec.dataset_id / ingest_id
    payload_path = snapshot_dir / "payload.parquet"
    metadata_path = snapshot_dir / "metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("content_hash") != content_hash:
            raise ValueError(f"immutable raw snapshot conflict for {ingest_id}")
        return {
            "ok": True,
            "ingest_id": ingest_id,
            "payload_path": str(payload_path),
            "metadata_path": str(metadata_path),
            "content_hash": content_hash,
            "retrieved_at": metadata.get("retrieved_at", ""),
            "reused": True,
        }

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(payload_path, index=False)
    snapshot_retrieved_at = retrieved_at or _now()
    metadata = {
        "source_id": source.source_id,
        "provider": source.provider,
        "dataset_id": spec.dataset_id,
        "ingest_id": ingest_id,
        "retrieved_at": snapshot_retrieved_at,
        "row_count": int(len(frame)),
        "content_hash": content_hash,
        "schema_hash": hashlib.sha256(
            json.dumps({"columns": list(frame.columns), "dtypes": [str(dtype) for dtype in frame.dtypes]}, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "request_summary": _redact_request_summary(request_summary or {}),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "ingest_id": ingest_id,
        "payload_path": str(payload_path),
        "metadata_path": str(metadata_path),
        "content_hash": content_hash,
        "retrieved_at": snapshot_retrieved_at,
        "reused": False,
    }


def read_global_raw_snapshot(
    *,
    source: SourceSpec,
    spec: DatasetSpec,
    ingest_id: str,
    root: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load an immutable raw snapshot for deterministic normalize/validate replay."""
    snapshot_dir = global_raw_base_path(root) / source.source_id / spec.dataset_id / ingest_id
    payload_path = snapshot_dir / "payload.parquet"
    metadata_path = snapshot_dir / "metadata.json"
    if not payload_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(f"global raw snapshot not found: {ingest_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("source_id") != source.source_id or metadata.get("dataset_id") != spec.dataset_id:
        raise ValueError(f"raw snapshot admission mismatch: {ingest_id}")
    return pd.read_parquet(payload_path), metadata


def write_global_quarantine(
    frame: pd.DataFrame,
    *,
    source: SourceSpec,
    spec: DatasetSpec,
    ingest_id: str,
    root: str | Path | None = None,
) -> dict[str, Any]:
    if frame.empty:
        return {"count": 0, "path": ""}
    path = global_quarantine_base_path(root) / source.source_id / spec.dataset_id / ingest_id / "rows.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return {"count": int(len(frame)), "path": str(path)}


def read_global_manifest(root: str | Path | None = None) -> dict[str, Any]:
    path = global_manifest_path(root)
    if not path.exists():
        return {"generated_at": "", "datasets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_global_manifest(manifest: dict[str, Any], root: str | Path | None = None) -> None:
    path = global_manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_value(frame: pd.DataFrame, spec: DatasetSpec) -> str:
    col = spec.date_column
    if col not in frame.columns or frame.empty:
        return ""
    values = frame[col].dropna()
    if values.empty:
        return ""
    if col == "month":
        return str(values.astype(str).max())
    try:
        return pd.to_datetime(values).max().date().isoformat()
    except Exception:
        return str(values.astype(str).max())


def _latest_timestamp(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns or frame.empty:
        return ""
    values = pd.to_datetime(frame[column], errors="coerce", utc=True).dropna()
    if values.empty:
        return ""
    return values.max().isoformat(timespec="seconds")


def _coverage(frame: pd.DataFrame, source: SourceSpec, spec: DatasetSpec) -> dict[str, Any]:
    key = "series_id" if spec.asset_class in {"macro", "rates"} else spec.symbol_column
    expected = sorted(source.allowlist_for(spec.dataset_id))
    received = sorted(set(frame[key].dropna().astype(str))) if key and key in frame.columns else []
    missing = sorted(set(expected) - set(received))
    return {
        "expected": len(expected),
        "received": len(received),
        "ratio": len(set(expected) & set(received)) / len(expected) if expected else 0.0,
        "missing": missing,
    }


def _write_global_dataset(
    frame: pd.DataFrame,
    spec: DatasetSpec,
    *,
    root: str | Path | None = None,
    status: str = "available",
    last_error: str = "",
    source: SourceSpec | None = None,
    quality_status: str = "available",
    quarantine_count: int = 0,
    raw_hash: str = "",
    canonical_hash: str = "",
    ingest_id: str = "",
) -> dict[str, Any]:
    path = global_dataset_path(spec, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    out.to_parquet(path, index=False)

    manifest = read_global_manifest(root)
    manifest["generated_at"] = _now()
    datasets = manifest.setdefault("datasets", {})
    datasets[spec.dataset_id] = {
        "dataset_id": spec.dataset_id,
        "source_id": source.source_id if source else "",
        "provider": source.provider if source else spec.provider,
        "asset_class": spec.asset_class,
        "frequency": spec.frequency,
        "calendar": spec.calendar,
        "timezone": spec.timezone,
        "currency": spec.currency,
        "pit_policy": spec.pit_policy,
        "required": spec.required,
        "path": str(path),
        "row_count": int(len(out)),
        "latest_date": _latest_value(out, spec),
        "latest_observation": _latest_timestamp(out, "observed_at"),
        "latest_available": _latest_timestamp(out, "available_at"),
        "watermark": _latest_timestamp(out, "available_at"),
        "coverage": _coverage(out, source, spec) if source else {},
        "status": status,
        "quality_status": quality_status,
        "quarantine_count": quarantine_count,
        "raw_hash": raw_hash,
        "canonical_hash": canonical_hash or frame_content_hash(out),
        "last_good_ingest_id": ingest_id,
        "last_error": last_error,
        "updated_at": _now(),
    }
    write_global_manifest(manifest, root)
    return {"ok": True, **datasets[spec.dataset_id]}


def write_global_dataset(*args, **kwargs) -> dict[str, Any]:
    """Deprecated raw-frame writer guard.

    Callers must normalize and validate through ``write_validated_global_dataset``
    so provider responses cannot silently bypass the quality boundary.
    """
    raise RuntimeError("write_global_dataset requires validated canonical data; use write_validated_global_dataset")


def write_validated_global_dataset(
    validation: GlobalValidationResult,
    *,
    source: SourceSpec,
    spec: DatasetSpec,
    ingest_id: str,
    root: str | Path | None = None,
    raw_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write only a passed canonical batch and persist row-level quarantine."""
    if validation.rejected:
        raise ValueError(f"refusing rejected global batch: {','.join(validation.issues)}")
    if validation.clean.empty:
        raise ValueError("refusing empty validated global batch")
    if not validation.clean["ingest_id"].eq(ingest_id).all():
        raise ValueError("canonical ingest_id does not match raw snapshot")
    quarantine = write_global_quarantine(
        validation.quarantine,
        source=source,
        spec=spec,
        ingest_id=ingest_id,
        root=root,
    )
    path = global_dataset_path(spec, root)
    merged = validation.clean.copy()
    if path.exists():
        existing = pd.read_parquet(path)
        key = list(primary_key_for_dataset(spec))
        missing = sorted(set(key) - set(existing.columns))
        if missing:
            raise ValueError(f"existing canonical dataset is missing primary key columns: {','.join(missing)}")
        merged = pd.concat([existing, merged], ignore_index=True, sort=False)
        merged = merged.drop_duplicates(subset=key, keep="last")
    result = _write_global_dataset(
        merged,
        spec,
        root=root,
        status=validation.status,
        source=source,
        quality_status=validation.status,
        quarantine_count=quarantine["count"],
        raw_hash=(raw_snapshot or {}).get("content_hash", ""),
        canonical_hash=frame_content_hash(merged),
        ingest_id=ingest_id,
    )
    result["quarantine_path"] = quarantine["path"]
    return result


def record_global_dataset_status(
    spec: DatasetSpec,
    *,
    root: str | Path | None = None,
    status: str,
    last_error: str = "",
    row_count: int = 0,
    latest_date: str = "",
    source: SourceSpec | None = None,
) -> dict[str, Any]:
    manifest = read_global_manifest(root)
    manifest["generated_at"] = _now()
    datasets = manifest.setdefault("datasets", {})
    existing = dict(datasets.get(spec.dataset_id, {}))
    existing.update({
        "dataset_id": spec.dataset_id,
        "source_id": source.source_id if source else existing.get("source_id", ""),
        "provider": source.provider if source else spec.provider,
        "asset_class": spec.asset_class,
        "frequency": spec.frequency,
        "calendar": spec.calendar,
        "timezone": spec.timezone,
        "currency": spec.currency,
        "pit_policy": spec.pit_policy,
        "required": spec.required,
        "row_count": int(row_count or existing.get("row_count", 0) or 0),
        "latest_date": latest_date or existing.get("latest_date", ""),
        "status": status,
        "last_error": last_error,
        "updated_at": _now(),
    })
    datasets[spec.dataset_id] = existing
    write_global_manifest(manifest, root)
    return existing
