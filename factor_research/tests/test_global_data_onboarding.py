"""Tests for the global source-admission and cleaning boundary."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_source_admission_registry_is_complete_and_fails_closed():
    from lake.global_catalog import SOURCE_REGISTRY, apply_source_admission, validate_source_registry

    validate_source_registry()
    source = SOURCE_REGISTRY["alfred_macro_v1"]
    with pytest.raises(ValueError, match="available_at"):
        validate_source_registry({"alfred_macro_v1": replace(source, availability_field="observed_at")})
    approved = apply_source_admission(source, {
        "admission_status": "approved",
        "license_status": "approved",
        "license_checked_at": "2026-07-10",
    })
    assert approved.enabled is True
    with pytest.raises(ValueError, match="unsupported source admission"):
        apply_source_admission(source, {"provider": "other"})


def test_raw_snapshot_is_idempotent_and_redacts_sensitive_request_data(tmp_path):
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_writer import write_global_raw_snapshot

    frame = pd.DataFrame({"date": ["2026-07-01"], "value": [3.0]})
    source = get_source_spec("alfred_macro_v1")
    spec = get_dataset_spec("macro_daily")

    first = write_global_raw_snapshot(
        frame,
        source=source,
        spec=spec,
        root=tmp_path,
        request_summary={"series_id": "DFF", "api_key": "do-not-store"},
    )
    second = write_global_raw_snapshot(
        frame,
        source=source,
        spec=spec,
        root=tmp_path,
        request_summary={"series_id": "DFF", "api_key": "another-secret"},
    )

    assert first["ingest_id"] == second["ingest_id"]
    metadata = json.loads(Path(first["metadata_path"]).read_text(encoding="utf-8"))
    assert metadata["request_summary"]["api_key"] == "[redacted]"
    assert "do-not-store" not in Path(first["metadata_path"]).read_text(encoding="utf-8")


def test_macro_normalizer_requires_real_availability_metadata():
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame

    raw = pd.DataFrame({
        "series_id": ["DFF"],
        "observation_date": ["2026-07-01"],
        "value": [4.25],
        "unit": ["Percent"],
        "vintage_start": ["2026-07-01"],
        "vintage_end": ["9999-12-31"],
    })

    with pytest.raises(ValueError, match="available_at"):
        normalize_global_frame(
            raw,
            source=get_source_spec("alfred_macro_v1"),
            spec=get_dataset_spec("macro_daily"),
            retrieved_at="2026-07-02T00:00:00Z",
        )


def test_price_cleaning_quarantines_bad_ohlc_without_overwriting_last_good(tmp_path):
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame
    from lake.global_writer import write_validated_global_dataset

    spec = get_dataset_spec("etf_daily")
    source = replace(get_source_spec("global_etf_price_v1"), max_quarantine_ratio=0.6)
    raw = pd.DataFrame({
        "symbol": ["SPY", "QQQ"],
        "exchange": ["ARCX", "NASDAQ"],
        "session_date": ["2026-07-01", "2026-07-01"],
        "session_close_at": ["2026-07-01T20:00:00Z", "2026-07-01T20:00:00Z"],
        "open": [620.0, 550.0],
        "high": [625.0, 549.0],
        "low": [619.0, 548.0],
        "close": [624.0, 551.0],
        "volume": [1000, 2000],
        "is_adjusted": [False, False],
        "adjustment_version": ["raw-v1", "raw-v1"],
        "currency": ["USD", "USD"],
    })
    canonical = normalize_global_frame(
        raw,
        source=source,
        spec=spec,
        retrieved_at="2026-07-02T00:00:00Z",
        ingest_id="unit-ingest",
    )
    validated = validate_global_frame(canonical, source=source, spec=spec)

    assert validated.rejected is False
    assert len(validated.clean) == 1
    assert len(validated.quarantine) == 1
    assert "ohlc" in validated.quarantine.iloc[0]["_reason"]

    result = write_validated_global_dataset(
        validated,
        source=source,
        spec=spec,
        root=tmp_path,
        ingest_id="unit-ingest",
    )
    assert result["row_count"] == 1
    assert result["quarantine_count"] == 1
    assert Path(result["path"]).exists()


def test_conflicting_primary_keys_reject_the_full_batch():
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame

    spec = get_dataset_spec("etf_daily")
    source = get_source_spec("global_etf_price_v1")
    raw = pd.DataFrame({
        "symbol": ["SPY", "SPY"],
        "exchange": ["ARCX", "ARCX"],
        "session_date": ["2026-07-01", "2026-07-01"],
        "session_close_at": ["2026-07-01T20:00:00Z", "2026-07-01T20:00:00Z"],
        "open": [620.0, 620.0],
        "high": [625.0, 625.0],
        "low": [619.0, 619.0],
        "close": [624.0, 623.0],
        "volume": [1000, 1000],
        "is_adjusted": [False, False],
        "adjustment_version": ["raw-v1", "raw-v1"],
        "currency": ["USD", "USD"],
    })
    canonical = normalize_global_frame(
        raw,
        source=source,
        spec=spec,
        retrieved_at="2026-07-02T00:00:00Z",
        ingest_id="conflict-ingest",
    )
    validated = validate_global_frame(canonical, source=source, spec=spec)

    assert validated.rejected is True
    assert "primary key conflict" in validated.issues


def test_global_source_read_view_exposes_unapproved_admission_state(tmp_path, monkeypatch):
    from app_config.settings import Settings
    from services.read import global_data

    monkeypatch.setattr(global_data, "get_settings", lambda: Settings._from_dict({}))

    view = global_data.global_data_sources(root=tmp_path)
    macro = next(source for source in view.sources if source.dataset_id == "macro_daily")

    assert macro.source_id == "alfred_macro_v1"
    assert macro.status == "source_not_admitted"
    assert macro.allowed_use == "research_only"
    assert macro.availability_confidence == "date_only_conservative_end_of_source_day"


def test_unapproved_source_records_status_without_writing_canonical_data(tmp_path, monkeypatch):
    from app_config.settings import GlobalDataConfig
    from scripts.data import update_global_data

    monkeypatch.setattr(
        update_global_data,
        "_settings",
        lambda: GlobalDataConfig(enabled=True, datasets=("macro_daily",)),
    )

    result = update_global_data.run_global_update(
        root=tmp_path,
        dataset_ids=["macro_daily"],
        source_id="alfred_macro_v1",
    )

    detail = result["detail"]["macro_daily"]
    assert result["ok"] is False
    assert detail["status"] == "source_not_admitted"
    assert not (tmp_path / "data_lake/global/macro_daily.parquet").exists()
    assert (tmp_path / "data_lake/global_manifest.json").exists()


def test_all_enabled_respects_disabled_global_data_configuration(tmp_path, monkeypatch):
    from app_config.settings import GlobalDataConfig
    from scripts.data import update_global_data

    monkeypatch.setattr(update_global_data, "_settings", lambda: GlobalDataConfig())

    result = update_global_data.run_global_update(root=tmp_path, all_enabled=True)

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "global_data_disabled_or_no_datasets"
    assert not (tmp_path / "data_lake/global_manifest.json").exists()


def test_validated_incremental_write_merges_by_primary_key_and_advances_watermark(tmp_path):
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame
    from lake.global_writer import read_global_manifest, write_validated_global_dataset

    source = get_source_spec("global_etf_price_v1")
    spec = get_dataset_spec("etf_daily")

    def write(symbol: str, date: str, ingest_id: str) -> None:
        raw = pd.DataFrame({
            "symbol": [symbol],
            "exchange": ["ARCX"],
            "session_date": [date],
            "session_close_at": [f"{date}T20:00:00Z"],
            "open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0],
            "volume": [1000], "is_adjusted": [False], "adjustment_version": ["raw-v1"],
            "currency": ["USD"],
        })
        canonical = normalize_global_frame(
            raw,
            source=source,
            spec=spec,
            retrieved_at=f"{date}T23:00:00Z",
            ingest_id=ingest_id,
        )
        write_validated_global_dataset(
            validate_global_frame(canonical, source=source, spec=spec),
            source=source,
            spec=spec,
            ingest_id=ingest_id,
            root=tmp_path,
        )

    write("SPY", "2026-07-01", "first")
    write("QQQ", "2026-07-02", "second")

    meta = read_global_manifest(root=tmp_path)["datasets"]["etf_daily"]
    assert meta["row_count"] == 2
    assert meta["last_good_ingest_id"] == "second"
    assert meta["watermark"].startswith("2026-07-02")


def test_replay_ingest_reuses_raw_snapshot_without_provider_network_access(tmp_path):
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_writer import write_global_raw_snapshot
    from scripts.data.update_global_data import run_global_update

    source = replace(
        get_source_spec("global_etf_price_v1"),
        admission_status="approved",
        license_status="approved",
        license_checked_at="2026-07-10",
    )
    spec = get_dataset_spec("etf_daily")
    raw = pd.DataFrame({
        "symbol": ["SPY"], "exchange": ["ARCX"], "session_date": ["2026-07-01"],
        "session_close_at": ["2026-07-01T20:00:00Z"],
        "open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0],
        "volume": [1000], "is_adjusted": [False], "adjustment_version": ["raw-v1"], "currency": ["USD"],
    })
    snapshot = write_global_raw_snapshot(raw, source=source, spec=spec, root=tmp_path)

    result = run_global_update(
        root=tmp_path,
        dataset_ids=["etf_daily"],
        source=source,
        replay_ingest=snapshot["ingest_id"],
    )

    assert result["ok"] is True
    assert result["detail"]["etf_daily"]["replayed"] is True
    assert (tmp_path / "data_lake/global/etf_daily.parquet").exists()


def test_configured_source_admission_enables_ingestion_without_registry_edit(tmp_path, monkeypatch):
    from app_config.settings import GlobalDataConfig
    from scripts.data import update_global_data

    class FakeProvider:
        def probe(self, spec):
            return {"ok": True, "provider": "openbb", "dataset_id": spec.dataset_id, "status": "available"}

        def fetch(self, spec, *, start=None, end=None):
            return pd.DataFrame({
                "symbol": ["SPY"], "exchange": ["ARCX"], "session_date": ["2026-07-01"],
                "session_close_at": ["2026-07-01T20:00:00Z"],
                "open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0],
                "volume": [1000], "is_adjusted": [False], "adjustment_version": ["raw-v1"], "currency": ["USD"],
            })

    settings = GlobalDataConfig(
        enabled=True,
        datasets=("etf_daily",),
        source_admissions={
            "global_etf_price_v1": {
                "admission_status": "approved",
                "license_status": "approved",
                "license_checked_at": "2026-07-10",
            }
        },
    )
    monkeypatch.setattr(update_global_data, "_settings", lambda: settings)

    result = update_global_data.run_global_update(
        root=tmp_path,
        dataset_ids=["etf_daily"],
        source_id="global_etf_price_v1",
        provider=FakeProvider(),
    )

    assert result["ok"] is True
    assert result["detail"]["etf_daily"]["source_id"] == "global_etf_price_v1"


def test_from_watermark_rewinds_revision_window_before_fetch(tmp_path, monkeypatch):
    from app_config.settings import GlobalDataConfig
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame
    from lake.global_writer import write_validated_global_dataset
    from scripts.data import update_global_data

    source = replace(
        get_source_spec("global_etf_price_v1"),
        admission_status="approved",
        license_status="approved",
        license_checked_at="2026-07-10",
    )
    spec = get_dataset_spec("etf_daily")
    seed_raw = pd.DataFrame({
        "symbol": ["SPY"], "exchange": ["ARCX"], "session_date": ["2026-07-01"],
        "session_close_at": ["2026-07-01T20:00:00Z"],
        "open": [100.0], "high": [102.0], "low": [99.0], "close": [101.0],
        "volume": [1000], "is_adjusted": [False], "adjustment_version": ["raw-v1"], "currency": ["USD"],
    })
    seed = normalize_global_frame(seed_raw, source=source, spec=spec, retrieved_at="2026-07-01T23:00:00Z", ingest_id="seed")
    write_validated_global_dataset(
        validate_global_frame(seed, source=source, spec=spec),
        source=source,
        spec=spec,
        ingest_id="seed",
        root=tmp_path,
    )
    monkeypatch.setattr(update_global_data, "_settings", lambda: GlobalDataConfig(enabled=True, datasets=("etf_daily",)))

    class FakeProvider:
        def __init__(self):
            self.start = None

        def probe(self, spec):
            return {"ok": True, "provider": "openbb", "dataset_id": spec.dataset_id, "status": "available"}

        def fetch(self, spec, *, start=None, end=None):
            self.start = start
            return seed_raw

    provider = FakeProvider()
    result = update_global_data.run_global_update(
        root=tmp_path,
        dataset_ids=["etf_daily"],
        provider=provider,
        source=source,
        from_watermark=True,
    )

    assert result["ok"] is True
    assert provider.start == "2026-06-26"
