"""Global multi-asset data infrastructure tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_global_data_settings_defaults_disabled_non_required():
    from app_config.settings import Settings

    default = Settings._from_dict({})
    assert default.global_data.enabled is False
    assert default.global_data.required is False
    assert default.global_data.provider_mode == "openbb"
    assert default.global_data.datasets == ()
    assert default.global_data.source_admissions == {}
    assert Settings._from_dict({"global_data": None}).global_data.enabled is False

    configured = Settings._from_dict({
        "global_data": {
            "enabled": True,
            "required": True,
            "provider_mode": "openbb",
            "datasets": ["macro_daily", "fx_daily"],
            "api_key_envs": {"fmp": "FMP_API_KEY"},
            "source_admissions": {
                "alfred_macro_v1": {
                    "admission_status": "approved",
                    "license_status": "approved",
                    "license_checked_at": "2026-07-10",
                }
            },
            "max_daily_failures": 2,
        }
    })
    assert configured.global_data.enabled is True
    assert configured.global_data.required is True
    assert configured.global_data.datasets == ("macro_daily", "fx_daily")
    assert configured.global_data.api_key_envs["fmp"] == "FMP_API_KEY"
    assert configured.global_data.source_admissions["alfred_macro_v1"]["admission_status"] == "approved"
    assert configured.global_data.max_daily_failures == 2


def test_repository_settings_admit_alfred_as_auxiliary_research_data():
    from app_config.settings import Settings

    settings = Settings.from_yaml(str(ROOT / "app_config" / "settings.yaml"))
    global_data = settings.global_data

    assert global_data.enabled is True
    assert global_data.required is False
    assert global_data.provider_mode == "alfred"
    assert global_data.datasets == (
        "macro_daily", "macro_monthly", "rates_daily",
        "market_price_daily", "etf_daily", "fx_daily", "commodity_daily",
    )
    assert global_data.api_key_envs == {"alfred": "FRED_API_KEY"}
    admission = global_data.source_admissions["alfred_macro_v1"]
    assert admission["admission_status"] == "approved"
    assert admission["license_status"] == "approved"
    assert admission["allowed_use"] == "research_only"
    assert global_data.source_admissions["global_cboe_us_price_v1"]["admission_status"] == "approved"
    assert global_data.source_admissions["global_yfinance_fx_v1"]["admission_status"] == "approved"
    assert global_data.source_admissions["global_yfinance_commodity_v1"]["admission_status"] == "approved"


def test_global_dataset_registry_declares_required_pit_metadata():
    from lake.global_catalog import DATASET_REGISTRY, get_dataset_spec, validate_dataset_registry

    expected = {
        "macro_daily",
        "macro_monthly",
        "market_price_daily",
        "etf_daily",
        "fx_daily",
        "rates_daily",
        "commodity_daily",
        "derivatives_daily",
        "news_events",
        "regulatory_filings",
    }
    assert expected.issubset(DATASET_REGISTRY)
    validate_dataset_registry()

    for dataset_id in expected:
        spec = get_dataset_spec(dataset_id)
        assert spec.dataset_id == dataset_id
        assert spec.asset_class
        assert spec.provider
        assert spec.frequency
        assert spec.calendar
        assert spec.timezone
        assert spec.currency
        assert spec.pit_policy
        assert spec.required is False


def test_openbb_provider_missing_package_returns_structured_unavailable():
    from lake.global_catalog import get_dataset_spec
    from lake.sources.openbb_global import OpenBBGlobalProvider

    def missing_import(_: str):
        raise ModuleNotFoundError("No module named 'openbb'")

    provider = OpenBBGlobalProvider(importer=missing_import, api_key_envs={})
    status = provider.probe(get_dataset_spec("macro_daily"))

    assert status["ok"] is False
    assert status["status"] == "provider_unavailable"
    assert status["provider"] == "openbb"
    assert "openbb" in status["error"].lower()


def test_openbb_source_without_key_is_not_given_unrelated_provider_key(monkeypatch):
    from dataclasses import replace

    from lake.global_catalog import get_source_spec
    from scripts.data import update_global_data

    captured = {}

    class FakeOpenBBProvider:
        def __init__(self, *, api_key_envs, source):
            captured["api_key_envs"] = api_key_envs
            captured["source"] = source

    monkeypatch.setattr(update_global_data, "OpenBBGlobalProvider", FakeOpenBBProvider)

    source = replace(
        get_source_spec("global_yfinance_fx_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
    )
    update_global_data._provider(provider_mode="openbb", api_key_envs={"alfred": "FRED_API_KEY"}, source=source)

    assert captured["api_key_envs"] == {}
    assert captured["source"] == source


def test_openbb_yfinance_maps_prices_and_fx_to_conservative_canonical_raw_frames():
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.sources.openbb_global import OpenBBGlobalProvider

    calls = []

    class Result:
        def __init__(self, symbol):
            self.symbol = symbol

        def to_df(self):
            return pd.DataFrame(
                {
                    "open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5],
                    "volume": [1000.0], "symbol": [self.symbol],
                },
                index=pd.DatetimeIndex(["2025-01-02"], name="date"),
            )

    class Historical:
        def __init__(self, kind):
            self.kind = kind

        def __call__(self, **kwargs):
            calls.append((self.kind, kwargs))
            return Result(kwargs["symbol"])

    class App:
        class equity:
            class price:
                historical = Historical("equity")

        class currency:
            class price:
                historical = Historical("currency")

    us_source = replace(
        get_source_spec("global_yfinance_us_price_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
    )
    us_provider = OpenBBGlobalProvider(importer=lambda _: App(), source=us_source)
    us_raw = us_provider.fetch(get_dataset_spec("etf_daily"), start="2025-01-01", end="2025-01-03")

    assert len(calls) == 11
    assert all(call[0] == "equity" for call in calls)
    assert all(call[1]["provider"] == "yfinance" for call in calls)
    assert all(call[1]["adjustment"] == "splits_only" for call in calls)
    assert us_raw.iloc[0]["symbol"] == "SPY"
    assert us_raw.iloc[0]["exchange"] == "YFINANCE_US"
    assert bool(us_raw.iloc[0]["is_adjusted"]) is True
    assert us_raw.iloc[0]["adjustment_version"] == "yfinance_splits_only_v1"
    assert str(us_raw.iloc[0]["available_at"]).endswith("+00:00")

    fx_source = replace(
        get_source_spec("global_yfinance_fx_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
    )
    fx_provider = OpenBBGlobalProvider(importer=lambda _: App(), source=fx_source)
    fx_raw = fx_provider.fetch(get_dataset_spec("fx_daily"), start="2025-01-01", end="2025-01-03")

    assert len(calls) == 17
    assert all(call[0] == "currency" for call in calls[11:])
    assert [call[1]["symbol"] for call in calls[11:]] == ["EURUSD=X", "USDJPY=X", "USDCNY=X", "GBPUSD=X", "AUDUSD=X", "USDCHF=X"]
    assert fx_raw.iloc[0]["symbol"] == "EURUSD"
    assert fx_raw.iloc[0]["exchange"] == "YFINANCE_FX"
    assert fx_raw.iloc[0]["currency"] == "PAIR"


def test_openbb_options_probe_is_blocked_until_historical_dates_are_verified():
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.sources.openbb_global import OpenBBGlobalProvider

    source = replace(
        get_source_spec("cboe_options_chain_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
    )
    status = OpenBBGlobalProvider(importer=lambda _: object(), source=source).probe(
        get_dataset_spec("derivatives_daily")
    )

    assert status["ok"] is False
    assert status["status"] == "historical_date_unverified"
    assert "PIT ingestion is blocked" in status["error"]


def test_global_writer_manifest_and_price_loader(tmp_path):
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_data import load_global_price_panel
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame
    from lake.global_writer import read_global_manifest, write_validated_global_dataset

    spec = get_dataset_spec("market_price_daily")
    frame = pd.DataFrame({
        "date": ["2026-07-06", "2026-07-07", "2026-07-06", "2026-07-07"],
        "symbol": ["SPY", "SPY", "QQQ", "QQQ"],
        "exchange": ["ARCX", "ARCX", "NASDAQ", "NASDAQ"],
        "session_close_at": ["2026-07-06T20:00:00Z", "2026-07-07T20:00:00Z", "2026-07-06T20:00:00Z", "2026-07-07T20:00:00Z"],
        "open": [619.0, 620.0, 549.0, 550.0],
        "high": [621.0, 622.0, 551.0, 553.0],
        "low": [618.0, 619.0, 548.0, 549.0],
        "close": [620.0, 621.5, 550.0, 552.0],
        "volume": [1000, 1100, 900, 950],
        "is_adjusted": [False, False, False, False],
        "adjustment_version": ["raw-v1", "raw-v1", "raw-v1", "raw-v1"],
        "currency": ["USD", "USD", "USD", "USD"],
    })
    source = get_source_spec("global_cboe_us_price_v1")
    canonical = normalize_global_frame(
        frame,
        source=source,
        spec=spec,
        retrieved_at="2026-07-08T00:00:00Z",
        ingest_id="price-unit",
    )
    result = write_validated_global_dataset(
        validate_global_frame(canonical, source=source, spec=spec),
        source=source,
        spec=spec,
        ingest_id="price-unit",
        root=tmp_path,
    )
    assert result["ok"] is True
    assert Path(result["path"]).exists()

    manifest = read_global_manifest(root=tmp_path)
    assert manifest["datasets"]["market_price_daily"]["row_count"] == 4
    assert manifest["datasets"]["market_price_daily"]["latest_date"] == "2026-07-07"
    assert manifest["datasets"]["market_price_daily"]["calendar"] == "US_EQUITIES"
    assert manifest["datasets"]["market_price_daily"]["timezone"] == "America/New_York"
    assert manifest["datasets"]["market_price_daily"]["currency"] == "USD"

    with pytest.raises(ValueError, match="adjustment_basis"):
        load_global_price_panel("market_price_daily", root=tmp_path, field="close")
    close = load_global_price_panel(
        "market_price_daily",
        root=tmp_path,
        field="close",
        adjustment_basis="raw",
    )
    assert list(close.columns) == ["QQQ", "SPY"]
    assert close.loc[pd.Timestamp("2026-07-07"), "SPY"] == 621.5


def test_adjusted_only_price_source_rejects_raw_price_loader(tmp_path):
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_data import load_global_price_panel
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame
    from lake.global_writer import write_validated_global_dataset

    spec = get_dataset_spec("etf_daily")
    source = replace(
        get_source_spec("global_yfinance_us_price_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
    )
    raw = pd.DataFrame({
        "session_date": ["2026-07-07"], "symbol": ["SPY"], "exchange": ["YFINANCE_US"],
        "session_close_at": ["2026-07-08T03:59:59Z"], "available_at": ["2026-07-08T03:59:59Z"],
        "open": [620.0], "high": [622.0], "low": [619.0], "close": [621.5], "volume": [1000],
        "is_adjusted": [True], "adjustment_version": ["yfinance_splits_only_v1"], "currency": ["USD"],
    })
    canonical = normalize_global_frame(raw, source=source, spec=spec, ingest_id="adjusted-only")
    validation = validate_global_frame(canonical, source=source, spec=spec)
    assert validation.rejected is False
    write_validated_global_dataset(validation, source=source, spec=spec, ingest_id="adjusted-only", root=tmp_path)

    with pytest.raises(ValueError, match="does not provide raw prices"):
        load_global_price_panel("etf_daily", root=tmp_path, adjustment_basis="raw")
    adjusted = load_global_price_panel("etf_daily", root=tmp_path, adjustment_basis="adjusted")
    assert adjusted.iloc[0, 0] == 621.5


def test_cboe_rounding_tolerance_does_not_quarantine_valid_ohlc_boundary():
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame

    source = replace(get_source_spec("global_cboe_us_price_v1"), admission_status="approved", license_status="approved", license_checked_at="2026-07-12")
    raw = pd.DataFrame({"date": ["2025-01-02"], "symbol": ["AAPL"], "exchange": ["CBOE_US"], "session_close_at": ["2025-01-03T04:59:59Z"], "open": [40.02], "high": [40.00], "low": [38.66], "close": [38.83], "volume": [1], "is_adjusted": [True], "adjustment_version": ["cboe_eod_research_v1"], "currency": ["USD"]})
    result = validate_global_frame(normalize_global_frame(raw, source=source, spec=get_dataset_spec("market_price_daily"), ingest_id="cboe-rounding"), source=source, spec=get_dataset_spec("market_price_daily"))
    assert result.rejected is False
    assert result.quarantine.empty


def test_global_macro_loader_uses_available_at_as_of_alignment(tmp_path):
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_data import load_global_macro
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame
    from lake.global_writer import write_validated_global_dataset

    spec = get_dataset_spec("macro_monthly")
    frame = pd.DataFrame({
        "series_id": ["CPIAUCSL", "CPIAUCSL"],
        "observation_date": ["2026-04-01", "2026-05-01"],
        "value": [2.0, 3.0],
        "unit": ["Index", "Index"],
        "vintage_start": ["2026-06-01", "2026-07-01"],
        "vintage_end": ["9999-12-31", "9999-12-31"],
        "available_at": ["2026-06-01T13:30:00Z", "2026-07-01T13:30:00Z"],
    })
    source = get_source_spec("alfred_macro_v1")
    canonical = normalize_global_frame(
        frame,
        source=source,
        spec=spec,
        retrieved_at="2026-07-02T00:00:00Z",
        ingest_id="macro-unit",
    )
    write_validated_global_dataset(
        validate_global_frame(canonical, source=source, spec=spec),
        source=source,
        spec=spec,
        ingest_id="macro-unit",
        root=tmp_path,
    )

    trade_dates = pd.to_datetime(["2026-05-31", "2026-06-15", "2026-06-30", "2026-07-01"])
    aligned = load_global_macro(
        "macro_monthly",
        trade_dates,
        root=tmp_path,
        fields=["value"],
        as_of_date="23:59:59",
    )

    assert pd.isna(aligned.loc[pd.Timestamp("2026-05-31"), "value"])
    assert aligned.loc[pd.Timestamp("2026-06-15"), "value"] == 2.0
    assert aligned.loc[pd.Timestamp("2026-06-30"), "value"] == 2.0
    assert aligned.loc[pd.Timestamp("2026-07-01"), "value"] == 3.0

    before_release = load_global_macro(
        "macro_monthly",
        pd.to_datetime(["2026-07-01"]),
        root=tmp_path,
        fields=["value"],
        as_of_date="08:00:00",
    )
    assert before_release.iloc[0]["value"] == 2.0


def test_update_global_data_uses_fake_provider_and_writes_manifest(tmp_path):
    from dataclasses import replace

    from lake.global_catalog import get_source_spec
    from scripts.data.update_global_data import run_global_update

    class FakeProvider:
        def probe(self, spec):
            return {"ok": True, "provider": "fake", "dataset_id": spec.dataset_id, "status": "available"}

        def fetch(self, spec, *, start=None, end=None):
            return pd.DataFrame({
                "date": ["2026-07-07"],
                "symbol": ["SPY"],
                "exchange": ["ARCX"],
                "session_close_at": ["2026-07-07T20:00:00Z"],
                "open": [620.0],
                "high": [622.0],
                "low": [619.0],
                "close": [621.5],
                "volume": [1000],
                "is_adjusted": [False],
                "adjustment_version": ["raw-v1"],
                "currency": ["USD"],
            })

    source = replace(
        get_source_spec("global_etf_price_v1"),
        admission_status="approved",
        license_status="approved",
        license_checked_at="2026-07-10",
    )
    result = run_global_update(
        root=tmp_path,
        dataset_ids=["market_price_daily"],
        provider=FakeProvider(),
        source=source,
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["required"] is False
    assert result["detail"]["market_price_daily"]["ok"] is True
    manifest = json.loads((tmp_path / "data_lake/global_manifest.json").read_text(encoding="utf-8"))
    assert manifest["datasets"]["market_price_daily"]["row_count"] == 1


def test_update_global_data_selects_configured_yfinance_source_over_planned_source(tmp_path, monkeypatch):
    from app_config.settings import GlobalDataConfig
    from scripts.data import update_global_data

    class FakeProvider:
        def probe(self, spec):
            return {"ok": True, "provider": "fake", "dataset_id": spec.dataset_id, "status": "available"}

        def fetch(self, spec, *, start=None, end=None):
            return pd.DataFrame({
                "date": ["2026-07-07"], "symbol": ["SPY"], "exchange": ["YFINANCE_US"],
                "session_close_at": ["2026-07-08T03:59:59Z"], "open": [620.0], "high": [622.0],
                "low": [619.0], "close": [621.5], "volume": [1000], "is_adjusted": [True],
                "adjustment_version": ["yfinance_splits_only_v1"], "currency": ["USD"],
            })

    monkeypatch.setattr(update_global_data, "_settings", lambda: GlobalDataConfig(
        enabled=True,
        source_admissions={
            "global_yfinance_us_price_v1": {
                "admission_status": "approved", "license_status": "approved", "license_checked_at": "2026-07-12",
            }
        },
    ))
    result = update_global_data.run_global_update(
        root=tmp_path,
        dataset_ids=["etf_daily"],
        provider=FakeProvider(),
        start="2026-07-07",
    )

    assert result["ok"] is True
    assert result["detail"]["etf_daily"]["source_id"] == "global_yfinance_us_price_v1"


def test_update_global_data_dry_run_does_not_write_manifest(tmp_path):
    from scripts.data.update_global_data import run_global_update

    class MissingProvider:
        def probe(self, spec):
            return {"ok": False, "provider": "fake", "dataset_id": spec.dataset_id, "status": "missing_credentials"}

    result = run_global_update(
        root=tmp_path,
        dataset_ids=["macro_daily"],
        provider=MissingProvider(),
        dry_run=True,
    )

    assert result["ok"] is False
    assert not (tmp_path / "data_lake/global_manifest.json").exists()


def test_scheduler_treats_non_required_global_failure_as_auxiliary_partial():
    from scripts.ops.scheduled_daily_update import compute_update_health, compute_final_status

    report = {
        "price_update": {"ok": True},
        "fundamental_update": {"ok": True},
        "etf_update": {"ok": True},
        "raw_update": {"ok": True},
        "tushare_incremental": {"ok": True},
        "global_data_update": {"ok": False, "required": False, "error": "openbb not installed"},
    }
    health = compute_update_health(report)

    assert health["core_update_ok"] is True
    assert health["aux_update_ok"] is False
    assert health["global_update_ok"] is False
    assert health["global_update_required"] is False
    assert compute_final_status(fresh=True, signal_ok=True, aux_update_ok=False, force=False) == "partial_ok"


def test_scheduler_required_global_failure_fails_final_status():
    from scripts.ops.scheduled_daily_update import compute_update_health, compute_final_status

    report = {
        "price_update": {"ok": True},
        "fundamental_update": {"ok": True},
        "etf_update": {"ok": True},
        "raw_update": {"ok": True},
        "tushare_incremental": {"ok": True},
        "global_data_update": {"ok": False, "required": True, "error": "entitlement missing"},
    }
    health = compute_update_health(report)

    assert health["required_update_ok"] is False
    assert compute_final_status(
        fresh=True,
        signal_ok=True,
        aux_update_ok=False,
        required_update_ok=False,
        force=False,
    ) == "failed"


def test_api_contracts_include_global_data_views():
    from contracts.views import (
        GlobalDataCoverageView,
        GlobalDataProbeRequest,
        GlobalDataSourceView,
        GlobalDataSourcesView,
    )

    source = GlobalDataSourceView(
        dataset_id="macro_daily",
        provider="openbb",
        asset_class="macro",
        status="missing_credentials",
        required=False,
    )
    view = GlobalDataSourcesView(sources=[source], summary={"total": 1})
    coverage = GlobalDataCoverageView(datasets=[{"dataset_id": "macro_daily"}])
    request = GlobalDataProbeRequest(dataset_id="macro_daily")

    assert view.sources[0].dataset_id == "macro_daily"
    assert coverage.datasets[0]["dataset_id"] == "macro_daily"
    assert request.dataset_id == "macro_daily"


def test_lake_writer_guard_flags_direct_global_lake_writes_outside_data_layer():
    from scripts.ci.check_lake_writers import scan_source

    src = """
from pathlib import Path
store = Path("data_lake") / "global" / "macro_daily"
df.to_parquet(store / "latest.parquet")
"""
    assert scan_source(src, rel="workflow/global_probe.py") == ["workflow/global_probe.py"]
