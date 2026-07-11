"""Read-side views for global multi-asset data state."""
from __future__ import annotations

from pathlib import Path

from app_config.settings import get_settings
from contracts.views import GlobalDataCoverageView, GlobalDataSourceView, GlobalDataSourcesView
from lake.global_catalog import DATASET_REGISTRY, apply_source_admission, get_source_for_dataset, get_source_spec
from lake.global_writer import read_global_manifest

ROOT = Path(__file__).resolve().parents[2]


def _summary(sources: list[GlobalDataSourceView]) -> dict:
    counts: dict[str, int] = {"total": len(sources)}
    for source in sources:
        counts[source.status] = counts.get(source.status, 0) + 1
    counts["available"] = counts.get("available", 0)
    return counts


def global_data_sources(*, root: str | Path | None = None) -> GlobalDataSourcesView:
    manifest = read_global_manifest(root or ROOT)
    datasets = manifest.get("datasets", {}) or {}
    sources: list[GlobalDataSourceView] = []
    for dataset_id, spec in DATASET_REGISTRY.items():
        meta = datasets.get(dataset_id, {}) or {}
        source_id = str(meta.get("source_id") or "")
        try:
            source = get_source_spec(source_id) if source_id else get_source_for_dataset(dataset_id)
            source = apply_source_admission(
                source,
                get_settings().global_data.source_admissions.get(source.source_id),
            )
        except KeyError:
            source = None
        status = str(meta.get("status") or ("source_not_admitted" if source and not source.enabled else "not_loaded"))
        sources.append(GlobalDataSourceView(
            dataset_id=dataset_id,
            source_id=source.source_id if source else source_id,
            provider=str(meta.get("provider") or (source.provider if source else spec.provider)),
            allowed_use=source.allowed_use if source else "research_only",
            admission_status=source.admission_status if source else "unknown",
            license_status=source.license_status if source else "unknown",
            availability_confidence=source.availability_confidence if source else "unknown",
            asset_class=spec.asset_class,
            frequency=spec.frequency,
            calendar=spec.calendar,
            timezone=spec.timezone,
            currency=spec.currency,
            pit_policy=spec.pit_policy,
            status=status,
            required=bool(meta.get("required", spec.required)),
            latest_date=str(meta.get("latest_date") or ""),
            latest_observation=str(meta.get("latest_observation") or meta.get("latest_date") or ""),
            latest_available=str(meta.get("latest_available") or ""),
            last_good_ingest_id=str(meta.get("last_good_ingest_id") or ""),
            row_count=int(meta.get("row_count") or 0),
            coverage=dict(meta.get("coverage") or {}),
            quality_status=str(meta.get("quality_status") or status),
            quarantine_count=int(meta.get("quarantine_count") or 0),
            last_error=str(meta.get("last_error") or ""),
            updated_at=str(meta.get("updated_at") or ""),
        ))
    return GlobalDataSourcesView(
        generated_at=str(manifest.get("generated_at") or ""),
        sources=sources,
        summary=_summary(sources),
    )


def global_data_coverage(*, root: str | Path | None = None) -> GlobalDataCoverageView:
    sources = global_data_sources(root=root)
    return GlobalDataCoverageView(
        generated_at=sources.generated_at,
        datasets=[source.model_dump() for source in sources.sources],
        summary=sources.summary,
    )
