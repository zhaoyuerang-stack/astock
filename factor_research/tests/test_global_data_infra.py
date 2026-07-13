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
    assert global_data.source_admissions["global_fmp_fx_v1"]["admission_status"] == "approved"
    assert global_data.source_admissions["alpha_vantage_commodity_spot_v1"]["admission_status"] == "approved"
    assert global_data.source_admissions["global_yfinance_fx_v1"]["admission_status"] == "planned"
    assert global_data.source_admissions["global_yfinance_commodity_v1"]["admission_status"] == "planned"


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


def test_openbb_fmp_fx_preserves_native_pair_symbols():
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
                    "open": [1.03], "high": [1.04], "low": [1.02], "close": [1.025],
                    "volume": [1000.0], "symbol": [self.symbol],
                },
                index=pd.DatetimeIndex(["2025-01-02"], name="date"),
            )

    class Historical:
        def __call__(self, **kwargs):
            calls.append(kwargs)
            return Result(kwargs["symbol"])

    class App:
        class currency:
            class price:
                historical = Historical()

    source = replace(
        get_source_spec("global_fmp_fx_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
    )
    provider = OpenBBGlobalProvider(importer=lambda _: App(), source=source)
    raw = provider.fetch(get_dataset_spec("fx_daily"), start="2025-01-01", end="2025-01-03")

    assert [call["symbol"] for call in calls] == ["EURUSD", "USDJPY", "USDCNY", "GBPUSD", "AUDUSD", "USDCHF"]
    assert all(call["provider"] == "fmp" for call in calls)
    assert raw.iloc[0]["symbol"] == "EURUSD"
    assert raw.iloc[0]["exchange"] == "FMP_FX"
    assert bool(raw.iloc[0]["is_adjusted"]) is False
    assert raw.iloc[0]["adjustment_version"] == "fmp_unadjusted_v1"


def test_openbb_fmp_adjustment_override_marks_review_frame_as_adjusted():
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.sources.openbb_global import OpenBBGlobalProvider

    calls = []

    class Result:
        def to_df(self):
            return pd.DataFrame(
                {
                    "open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5],
                    "volume": [1000.0], "symbol": ["AAPL"],
                },
                index=pd.DatetimeIndex(["2025-01-02"], name="date"),
            )

    class Historical:
        def __call__(self, **kwargs):
            calls.append(kwargs)
            return Result()

    class App:
        class equity:
            class price:
                historical = Historical()

    source = replace(
        get_source_spec("global_fmp_us_price_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
        allowlist=("AAPL",),
        dataset_allowlists=(("market_price_daily", ("AAPL",)),),
    )
    provider = OpenBBGlobalProvider(importer=lambda _: App(), source=source)
    raw = provider.fetch(
        get_dataset_spec("market_price_daily"),
        start="2025-01-02",
        end="2025-01-03",
        adjustment_override="splits_only",
    )

    assert calls
    assert all(call["provider"] == "fmp" for call in calls)
    assert all(call["adjustment"] == "splits_only" for call in calls)
    assert bool(raw.iloc[0]["is_adjusted"]) is True
    assert raw.iloc[0]["adjustment_version"] == "fmp_splits_only_v1"


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


def test_fmp_source_is_admitted_only_for_verified_stock_panel():
    from lake.global_catalog import get_source_spec

    source = get_source_spec("global_fmp_us_price_v1")

    assert source.datasets == ("market_price_daily",)
    assert source.allowlist_for("market_price_daily") == ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META")
    assert source.allowlist_for("etf_daily") == ()


def test_fmp_fx_source_is_admitted_for_verified_pair_panel():
    from lake.global_catalog import get_source_spec

    source = get_source_spec("global_fmp_fx_v1")

    assert source.datasets == ("fx_daily",)
    assert source.allowlist_for("fx_daily") == ("EURUSD", "USDJPY", "USDCNY", "GBPUSD", "AUDUSD", "USDCHF")


def test_alpha_vantage_commodity_source_is_registered_as_planned_candidate():
    from lake.global_catalog import get_source_spec

    source = get_source_spec("alpha_vantage_commodity_spot_v1")

    assert source.provider == "alphavantage"
    assert source.datasets == ("commodity_daily",)
    assert source.allowlist_for("commodity_daily") == ("CL=F", "BZ=F", "NG=F", "GC=F", "SI=F")


def test_alpha_vantage_commodity_provider_maps_close_only_spot_series():
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame
    from lake.sources.alpha_vantage_commodity import AlphaVantageCommodityProvider

    def fake_request(params):
        payloads = {
            "WTI": {"data": [{"date": "2025-01-02", "value": "73.13"}]},
            "BRENT": {"data": [{"date": "2025-01-02", "value": "75.11"}]},
            "NATURAL_GAS": {"data": [{"date": "2025-01-02", "value": "3.24"}]},
            "GOLD_SILVER_HISTORY:GOLD": {"data": [{"date": "2025-01-02", "price": "2645.2"}]},
            "GOLD_SILVER_HISTORY:SILVER": {"data": [{"date": "2025-01-02", "price": "29.8"}]},
        }
        key = params["function"] if params["function"] != "GOLD_SILVER_HISTORY" else f"{params['function']}:{params['symbol']}"
        return payloads[key]

    source = replace(
        get_source_spec("alpha_vantage_commodity_spot_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
    )
    provider = AlphaVantageCommodityProvider(
        source=source,
        environ={"ALPHAVANTAGE_API_KEY": "test"},
        request_json=fake_request,
    )
    raw = provider.fetch(get_dataset_spec("commodity_daily"), start="2025-01-01", end="2025-01-03")

    assert set(raw["symbol"]) == {"CL=F", "BZ=F", "NG=F", "GC=F", "SI=F"}
    canonical = normalize_global_frame(raw, source=source, spec=get_dataset_spec("commodity_daily"), ingest_id="commodity-unit")
    result = validate_global_frame(canonical, source=source, spec=get_dataset_spec("commodity_daily"))
    assert result.rejected is False
    assert result.quarantine.empty
    assert result.clean[["open", "high", "low"]].isna().all().all()
    assert result.clean.iloc[0]["ohlc_quality"] == "close_only_spot_series"


def test_commodity_validator_allows_negative_close_events():
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame

    spec = get_dataset_spec("commodity_daily")
    source = replace(
        get_source_spec("alpha_vantage_commodity_spot_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-13",
    )
    raw = pd.DataFrame({
        "session_date": ["2020-04-20"],
        "symbol": ["CL=F"],
        "exchange": ["ALPHAVANTAGE_SPOT"],
        "session_close_at": ["2020-04-20T23:59:59Z"],
        "available_at": ["2020-04-20T23:59:59Z"],
        "open": [pd.NA],
        "high": [pd.NA],
        "low": [pd.NA],
        "close": [-36.98],
        "volume": [0.0],
        "is_adjusted": [False],
        "adjustment_version": ["alphavantage_spot_v1"],
        "currency": ["USD"],
    })
    canonical = normalize_global_frame(raw, source=source, spec=spec, ingest_id="negative-commodity")
    result = validate_global_frame(canonical, source=source, spec=spec)

    assert result.rejected is False
    assert result.quarantine.empty
    assert result.clean.iloc[0]["close"] == -36.98


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
    source = get_source_spec("global_etf_price_v1")
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
    assert manifest["datasets"]["market_price_daily"]["calendar"] == "SOURCE_EXCHANGE"
    assert manifest["datasets"]["market_price_daily"]["timezone"] == "SOURCE_EXCHANGE"
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


def test_fx_writer_manifest_and_price_loader_uses_pair_symbol_column(tmp_path):
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_data import load_global_price_panel
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame
    from lake.global_writer import read_global_manifest, write_validated_global_dataset

    spec = get_dataset_spec("fx_daily")
    source = replace(
        get_source_spec("global_fmp_fx_v1"),
        admission_status="approved", license_status="approved", license_checked_at="2026-07-12",
    )
    raw = pd.DataFrame({
        "session_date": ["2026-07-07", "2026-07-08"],
        "symbol": ["EURUSD", "EURUSD"],
        "exchange": ["FMP_FX", "FMP_FX"],
        "session_close_at": ["2026-07-07T23:59:59Z", "2026-07-08T23:59:59Z"],
        "available_at": ["2026-07-07T23:59:59Z", "2026-07-08T23:59:59Z"],
        "open": [1.07, 1.08],
        "high": [1.08, 1.09],
        "low": [1.06, 1.07],
        "close": [1.075, 1.085],
        "volume": [1000, 1100],
        "is_adjusted": [False, False],
        "adjustment_version": ["fmp_unadjusted_v1", "fmp_unadjusted_v1"],
        "currency": ["PAIR", "PAIR"],
    })
    canonical = normalize_global_frame(raw, source=source, spec=spec, ingest_id="fx-unit")
    validation = validate_global_frame(canonical, source=source, spec=spec)
    assert validation.rejected is False
    write_validated_global_dataset(validation, source=source, spec=spec, ingest_id="fx-unit", root=tmp_path)

    manifest = read_global_manifest(root=tmp_path)
    assert manifest["datasets"]["fx_daily"]["coverage"]["received"] == 1
    assert manifest["datasets"]["fx_daily"]["coverage"]["missing"] == [
        "AUDUSD", "GBPUSD", "USDCHF", "USDCNY", "USDJPY"
    ]
    panel = load_global_price_panel("fx_daily", root=tmp_path, adjustment_basis="raw")
    assert list(panel.columns) == ["EURUSD"]
    assert panel.loc[pd.Timestamp("2026-07-08"), "EURUSD"] == 1.085


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


def test_cboe_source_is_canonicalized_as_close_only_when_ohlc_is_unverified():
    from dataclasses import replace

    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.global_normalizers import normalize_global_frame
    from lake.global_validator import validate_global_frame

    source = replace(get_source_spec("global_cboe_us_price_v1"), admission_status="approved", license_status="approved", license_checked_at="2026-07-12")
    raw = pd.DataFrame({"date": ["2025-01-02"], "symbol": ["AAPL"], "exchange": ["CBOE_US"], "session_close_at": ["2025-01-03T04:59:59Z"], "open": [40.02], "high": [40.00], "low": [38.66], "close": [38.83], "volume": [1], "is_adjusted": [True], "adjustment_version": ["cboe_eod_research_v1"], "currency": ["USD"]})
    result = validate_global_frame(normalize_global_frame(raw, source=source, spec=get_dataset_spec("market_price_daily"), ingest_id="cboe-rounding"), source=source, spec=get_dataset_spec("market_price_daily"))
    assert result.rejected is False
    assert result.quarantine.empty
    assert result.clean[["open", "high", "low"]].isna().all().all()
    assert result.clean.iloc[0]["ohlc_quality"] == "close_only_unverified_ohlc"


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


def test_update_global_data_prefers_admitted_fmp_fx_source(tmp_path):
    from scripts.data.update_global_data import run_global_update

    class FakeProvider:
        def probe(self, spec):
            return {"ok": True, "provider": "fake", "dataset_id": spec.dataset_id, "status": "available"}

        def fetch(self, spec, *, start=None, end=None, adjustment_override=None):
            return pd.DataFrame({
                "date": ["2026-07-07"],
                "symbol": ["EURUSD"],
                "exchange": ["FMP_FX"],
                "session_close_at": ["2026-07-07T23:59:59Z"],
                "available_at": ["2026-07-07T23:59:59Z"],
                "open": [1.07],
                "high": [1.08],
                "low": [1.06],
                "close": [1.075],
                "volume": [1000],
                "is_adjusted": [False],
                "adjustment_version": ["fmp_unadjusted_v1"],
                "currency": ["PAIR"],
            })

    result = run_global_update(
        root=tmp_path,
        dataset_ids=["fx_daily"],
        provider=FakeProvider(),
        start="2026-07-07",
    )

    assert result["ok"] is True
    assert result["detail"]["fx_daily"]["source_id"] == "global_fmp_fx_v1"


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


def test_price_reconciliation_classifies_adjustment_and_price_mismatches():
    from lake.global_reconciliation import prepare_price_observations, reconcile_price_observations

    primary = pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "AAPL", "MSFT", "MSFT"],
        "session_date": ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-02", "2025-01-03"],
        "adjusted_close": [100.0, 101.0, 102.0, 50.0, 51.0],
    })
    secondary = pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "AAPL", "MSFT", "MSFT"],
        "session_date": ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-02", "2025-01-03"],
        "adjusted_close": [100.0, 101.03, 204.0, 50.0, 51.0],
    })
    result = reconcile_price_observations(
        prepare_price_observations(primary, source_label="primary", price_column="adjusted_close"),
        prepare_price_observations(secondary, source_label="secondary", price_column="adjusted_close"),
        tolerance_bps=2.0,
        severe_bps=5000.0,
    )

    assert result.summary["aligned_rows"] == 5
    assert result.summary["price_mismatch_rows"] == 1
    assert result.summary["adjustment_or_unit_mismatch_rows"] == 1
    assert set(result.mismatches["classification"]) == {"price_mismatch", "adjustment_or_unit_mismatch"}


def test_reconcile_global_prices_uses_adjusted_close_review_path(monkeypatch):
    from scripts.data import reconcile_global_prices

    monkeypatch.setattr(
        reconcile_global_prices,
        "_select_primary",
        lambda *args, **kwargs: pd.DataFrame({
            "symbol": ["AAPL"],
            "session_date": ["2025-01-02"],
            "adjusted_close": [100.0],
            "source_id": ["global_cboe_us_price_v1"],
        }),
    )
    monkeypatch.setattr(
        reconcile_global_prices,
        "_fetch_secondary",
        lambda *args, **kwargs: pd.DataFrame({
            "symbol": ["AAPL"],
            "session_date": ["2025-01-02"],
            "adjusted_close": [100.0],
            "source_id": ["global_fmp_us_price_v1"],
        }),
    )

    report = reconcile_global_prices.run_reconciliation(start="2025-01-02")

    assert report["summary"]["ok"] is True
    assert report["summary"]["primary_source"] == "global_cboe_us_price_v1"
    assert report["summary"]["secondary_source"] == "global_fmp_us_price_v1"


def test_reconcile_global_prices_cli_returns_structured_failure(monkeypatch, capsys):
    from scripts.data import reconcile_global_prices

    monkeypatch.setattr(
        reconcile_global_prices,
        "run_reconciliation",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("not admitted")),
    )

    code = reconcile_global_prices.main(["--start", "2025-01-02", "--dataset", "etf_daily"])
    out = json.loads(capsys.readouterr().out)

    assert code == 1
    assert out["summary"]["ok"] is False
    assert out["summary"]["status"] == "reconciliation_failed"
    assert "not admitted" in out["summary"]["error"]
