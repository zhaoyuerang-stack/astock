"""Global multi-asset dataset catalog.

This registry describes what a dataset is allowed to mean before any provider
fetches data.  It is intentionally source-agnostic enough to add native
providers later, while keeping OpenBB as the first optional adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    label: str
    asset_class: str
    provider: str
    frequency: str
    calendar: str
    timezone: str
    currency: str
    pit_policy: str
    required: bool = False
    date_column: str = "date"
    symbol_column: str = ""
    storage_name: str = ""

    @property
    def storage_key(self) -> str:
        return self.storage_name or self.dataset_id


@dataclass(frozen=True)
class SourceSpec:
    """Admission record for a concrete global-data source.

    A dataset describes the semantic output.  A source record describes whether
    a provider is entitled and sufficiently specified to produce that output.
    Planned sources remain visible to health/probe surfaces but are not
    eligible for scheduled ingestion.
    """

    source_id: str
    provider: str
    adapter: str
    endpoint: str
    owner: str
    admission_status: str
    allowed_use: str
    license_status: str
    license_checked_at: str
    storage_restriction: str
    api_key_env: str
    datasets: tuple[str, ...]
    allowlist: tuple[str, ...]
    dataset_allowlists: tuple[tuple[str, tuple[str, ...]], ...]
    calendar: str
    timezone: str
    currency: str
    units: str
    raw_schema_version: str
    canonical_schema_version: str
    primary_key_policy: str
    dedupe_policy: str
    observed_field: str
    availability_field: str
    availability_confidence: str
    retrieved_field: str
    revision_policy: str
    corporate_action_policy: str
    max_quarantine_ratio: float = 0.02
    required: bool = False

    @property
    def enabled(self) -> bool:
        return self.admission_status == "approved" and self.license_status == "approved"

    def allowlist_for(self, dataset_id: str) -> tuple[str, ...]:
        for name, values in self.dataset_allowlists:
            if name == dataset_id:
                return values
        return ()


DATASET_REGISTRY: dict[str, DatasetSpec] = {
    "macro_daily": DatasetSpec(
        dataset_id="macro_daily",
        label="Global daily macro series",
        asset_class="macro",
        provider="openbb",
        frequency="daily",
        calendar="GLOBAL",
        timezone="UTC",
        currency="MIXED",
        pit_policy="daily_same_day_close",
    ),
    "macro_monthly": DatasetSpec(
        dataset_id="macro_monthly",
        label="Global monthly macro series",
        asset_class="macro",
        provider="openbb",
        frequency="monthly",
        calendar="GLOBAL",
        timezone="UTC",
        currency="MIXED",
        pit_policy="month_value_visible_m_plus_2",
        date_column="month",
    ),
    "market_price_daily": DatasetSpec(
        dataset_id="market_price_daily",
        label="Global equity/index daily prices",
        asset_class="equity_index",
        provider="openbb",
        frequency="daily",
        calendar="SOURCE_EXCHANGE",
        timezone="SOURCE_EXCHANGE",
        currency="SOURCE",
        pit_policy="daily_close_visible_after_market_close",
        symbol_column="symbol",
    ),
    "etf_daily": DatasetSpec(
        dataset_id="etf_daily",
        label="Global ETF daily prices",
        asset_class="etf",
        provider="openbb",
        frequency="daily",
        calendar="SOURCE_EXCHANGE",
        timezone="SOURCE_EXCHANGE",
        currency="SOURCE",
        pit_policy="daily_close_visible_after_market_close",
        symbol_column="symbol",
    ),
    "fx_daily": DatasetSpec(
        dataset_id="fx_daily",
        label="Foreign exchange daily rates",
        asset_class="fx",
        provider="openbb",
        frequency="daily",
        calendar="FX",
        timezone="UTC",
        currency="PAIR",
        pit_policy="daily_close_visible_after_market_close",
        symbol_column="pair",
    ),
    "rates_daily": DatasetSpec(
        dataset_id="rates_daily",
        label="Rates and fixed income daily series",
        asset_class="rates",
        provider="openbb",
        frequency="daily",
        calendar="GLOBAL",
        timezone="UTC",
        currency="SOURCE",
        pit_policy="daily_same_day_close",
        symbol_column="symbol",
    ),
    "commodity_daily": DatasetSpec(
        dataset_id="commodity_daily",
        label="Commodity daily prices",
        asset_class="commodity",
        provider="openbb",
        frequency="daily",
        calendar="SOURCE_EXCHANGE",
        timezone="SOURCE_EXCHANGE",
        currency="SOURCE",
        pit_policy="daily_close_visible_after_market_close",
        symbol_column="symbol",
    ),
    "derivatives_daily": DatasetSpec(
        dataset_id="derivatives_daily",
        label="Derivative and option daily data",
        asset_class="derivatives",
        provider="openbb",
        frequency="daily",
        calendar="SOURCE_EXCHANGE",
        timezone="SOURCE_EXCHANGE",
        currency="SOURCE",
        pit_policy="daily_close_visible_after_market_close",
        symbol_column="symbol",
    ),
    "news_events": DatasetSpec(
        dataset_id="news_events",
        label="News event stream",
        asset_class="news",
        provider="openbb",
        frequency="event",
        calendar="GLOBAL",
        timezone="UTC",
        currency="N/A",
        pit_policy="published_at_visible_only",
        date_column="published_at",
        symbol_column="symbol",
    ),
    "regulatory_filings": DatasetSpec(
        dataset_id="regulatory_filings",
        label="Regulatory filings",
        asset_class="regulatory",
        provider="openbb",
        frequency="event",
        calendar="REGULATOR",
        timezone="UTC",
        currency="N/A",
        pit_policy="accepted_at_visible_only",
        date_column="accepted_at",
        symbol_column="symbol",
    ),
}


# Concrete sources are deliberately separate from the dataset catalog.  These
# records are complete enough to audit planned work, but neither source is
# approved for automatic ingestion until credentials and source terms are
# verified by an owner.
SOURCE_REGISTRY: dict[str, SourceSpec] = {
    "alfred_macro_v1": SourceSpec(
        source_id="alfred_macro_v1",
        provider="alfred",
        adapter="lake.sources.alfred_macro.AlfredMacroProvider",
        endpoint="https://api.stlouisfed.org/fred/series/observations",
        owner="data-infrastructure",
        admission_status="planned",
        allowed_use="research_only",
        license_status="pending",
        license_checked_at="pending",
        storage_restriction="data_lake_only_no_redistribution",
        api_key_env="FRED_API_KEY",
        datasets=("macro_daily", "macro_monthly", "rates_daily"),
        allowlist=("DFF", "DGS2", "DGS10", "CPIAUCSL", "UNRATE", "INDPRO", "PAYEMS"),
        dataset_allowlists=(
            ("macro_daily", ("DFF",)),
            ("macro_monthly", ("CPIAUCSL", "UNRATE", "INDPRO", "PAYEMS")),
            ("rates_daily", ("DGS2", "DGS10")),
        ),
        calendar="US_FEDERAL_RESERVE",
        timezone="America/Chicago",
        currency="MIXED",
        units="source_series_metadata_required",
        raw_schema_version="alfred-observations-v1",
        canonical_schema_version="global-macro-v1",
        primary_key_policy="series_id_observation_date_vintage_start",
        dedupe_policy="identical_key_rows_dedup_conflicts_reject_batch",
        observed_field="observation_date",
        availability_field="available_at",
        availability_confidence="date_only_conservative_end_of_source_day",
        retrieved_field="retrieved_at",
        revision_policy="preserve_all_vintages",
        corporate_action_policy="not_applicable",
    ),
    "global_etf_price_v1": SourceSpec(
        source_id="global_etf_price_v1",
        provider="openbb",
        adapter="lake.sources.openbb_global.OpenBBGlobalProvider",
        endpoint="provider_defined_eod_ohlcv",
        owner="data-infrastructure",
        admission_status="planned",
        allowed_use="research_only",
        license_status="pending",
        license_checked_at="pending",
        storage_restriction="data_lake_only_no_redistribution",
        api_key_env="",
        datasets=("etf_daily", "market_price_daily"),
        allowlist=("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "HYG", "LQD", "GLD", "DBC", "UUP"),
        dataset_allowlists=(
            ("etf_daily", ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "HYG", "LQD", "GLD", "DBC", "UUP")),
            ("market_price_daily", ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "HYG", "LQD", "GLD", "DBC", "UUP")),
        ),
        calendar="SOURCE_EXCHANGE",
        timezone="SOURCE_EXCHANGE",
        currency="USD",
        units="provider_metadata_required",
        raw_schema_version="provider-ohlcv-v1",
        canonical_schema_version="global-price-v1",
        primary_key_policy="symbol_exchange_session_date_adjustment_version",
        dedupe_policy="identical_key_rows_dedup_conflicts_reject_batch",
        observed_field="session_date",
        availability_field="available_at",
        availability_confidence="session_close_conservative",
        retrieved_field="retrieved_at",
        revision_policy="preserve_adjustment_version",
        corporate_action_policy="raw_and_adjusted_fields_separate",
    ),
    "global_cboe_us_price_v1": SourceSpec(
        source_id="global_cboe_us_price_v1",
        provider="openbb",
        adapter="lake.sources.openbb_global.OpenBBGlobalProvider",
        endpoint="openbb.equity.price.historical(provider=cboe)",
        owner="data-infrastructure",
        admission_status="planned",
        allowed_use="research_only",
        license_status="pending",
        license_checked_at="pending",
        storage_restriction="data_lake_only_no_redistribution",
        api_key_env="",
        datasets=("market_price_daily", "etf_daily"),
        allowlist=("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "HYG", "LQD", "GLD", "DBC", "UUP"),
        dataset_allowlists=(("market_price_daily", ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META")), ("etf_daily", ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "HYG", "LQD", "GLD", "DBC", "UUP"))),
        calendar="US_EQUITIES",
        timezone="America/New_York",
        currency="USD",
        units="provider_ohlcv",
        raw_schema_version="openbb-cboe-ohlcv-v1",
        canonical_schema_version="global-price-v1",
        primary_key_policy="symbol_exchange_session_date_adjustment_version",
        dedupe_policy="identical_key_rows_dedup_conflicts_reject_batch",
        observed_field="session_date",
        availability_field="available_at",
        availability_confidence="date_only_conservative_end_of_source_day",
        retrieved_field="retrieved_at",
        revision_policy="provider_history_may_revise",
        corporate_action_policy="adjustment_semantics_not_valuation_eligible",
    ),
    "global_fmp_us_price_v1": SourceSpec(
        source_id="global_fmp_us_price_v1", provider="openbb", adapter="lake.sources.openbb_global.OpenBBGlobalProvider",
        endpoint="openbb.equity.price.historical(provider=fmp,adjustment=unadjusted)", owner="data-infrastructure",
        admission_status="planned", allowed_use="research_only", license_status="pending", license_checked_at="pending",
        storage_restriction="data_lake_only_no_redistribution", api_key_env="FMP_API_KEY",
        datasets=("market_price_daily",),
        allowlist=("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META"),
        dataset_allowlists=(("market_price_daily", ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META")),),
        calendar="US_EQUITIES", timezone="America/New_York", currency="USD", units="provider_ohlcv",
        raw_schema_version="openbb-fmp-ohlcv-v1", canonical_schema_version="global-price-v1",
        primary_key_policy="symbol_exchange_session_date_adjustment_version", dedupe_policy="identical_key_rows_dedup_conflicts_reject_batch",
        observed_field="session_date", availability_field="available_at", availability_confidence="date_only_conservative_end_of_source_day",
        retrieved_field="retrieved_at", revision_policy="provider_history_may_revise", corporate_action_policy="explicit_unadjusted_prices",
    ),
    "global_yfinance_us_price_v1": SourceSpec(
        source_id="global_yfinance_us_price_v1",
        provider="openbb",
        adapter="lake.sources.openbb_global.OpenBBGlobalProvider",
        endpoint="openbb.equity.price.historical(provider=yfinance)",
        owner="data-infrastructure",
        admission_status="planned",
        allowed_use="research_only",
        license_status="pending",
        license_checked_at="pending",
        storage_restriction="data_lake_only_no_redistribution",
        api_key_env="",
        datasets=("market_price_daily", "etf_daily"),
        allowlist=("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "HYG", "LQD", "GLD", "DBC", "UUP"),
        dataset_allowlists=(
            ("market_price_daily", ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META")),
            ("etf_daily", ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "HYG", "LQD", "GLD", "DBC", "UUP")),
        ),
        calendar="US_EQUITIES",
        timezone="America/New_York",
        currency="USD",
        units="provider_ohlcv",
        raw_schema_version="openbb-yfinance-ohlcv-v1",
        canonical_schema_version="global-price-v1",
        primary_key_policy="symbol_exchange_session_date_adjustment_version",
        dedupe_policy="identical_key_rows_dedup_conflicts_reject_batch",
        observed_field="session_date",
        availability_field="available_at",
        availability_confidence="date_only_conservative_end_of_source_day",
        retrieved_field="retrieved_at",
        revision_policy="provider_history_may_revise",
        corporate_action_policy="split_adjusted_only_no_unadjusted_price",
    ),
    "global_yfinance_fx_v1": SourceSpec(
        source_id="global_yfinance_fx_v1",
        provider="openbb",
        adapter="lake.sources.openbb_global.OpenBBGlobalProvider",
        endpoint="openbb.currency.price.historical(provider=yfinance)",
        owner="data-infrastructure",
        admission_status="planned",
        allowed_use="research_only",
        license_status="pending",
        license_checked_at="pending",
        storage_restriction="data_lake_only_no_redistribution",
        api_key_env="",
        datasets=("fx_daily",),
        allowlist=("EURUSD", "USDJPY", "USDCNY", "GBPUSD", "AUDUSD", "USDCHF"),
        dataset_allowlists=(("fx_daily", ("EURUSD", "USDJPY", "USDCNY", "GBPUSD", "AUDUSD", "USDCHF")),),
        calendar="FX",
        timezone="UTC",
        currency="PAIR",
        units="provider_ohlcv",
        raw_schema_version="openbb-yfinance-fx-v1",
        canonical_schema_version="global-price-v1",
        primary_key_policy="symbol_exchange_session_date_adjustment_version",
        dedupe_policy="identical_key_rows_dedup_conflicts_reject_batch",
        observed_field="session_date",
        availability_field="available_at",
        availability_confidence="date_only_conservative_end_of_source_day",
        retrieved_field="retrieved_at",
        revision_policy="provider_history_may_revise",
        corporate_action_policy="not_applicable",
    ),
    "global_yfinance_commodity_v1": SourceSpec(
        source_id="global_yfinance_commodity_v1",
        provider="openbb",
        adapter="lake.sources.openbb_global.OpenBBGlobalProvider",
        endpoint="openbb.equity.price.historical(provider=yfinance)",
        owner="data-infrastructure",
        admission_status="planned",
        allowed_use="research_only",
        license_status="pending",
        license_checked_at="pending",
        storage_restriction="data_lake_only_no_redistribution",
        api_key_env="",
        datasets=("commodity_daily",),
        allowlist=("CL=F", "GC=F", "SI=F", "HG=F"),
        dataset_allowlists=(("commodity_daily", ("CL=F", "GC=F", "SI=F", "HG=F")),),
        calendar="US_FUTURES",
        timezone="America/New_York",
        currency="USD",
        units="provider_ohlcv",
        raw_schema_version="openbb-yfinance-futures-v1",
        canonical_schema_version="global-price-v1",
        primary_key_policy="symbol_exchange_session_date_adjustment_version",
        dedupe_policy="identical_key_rows_dedup_conflicts_reject_batch",
        observed_field="session_date",
        availability_field="available_at",
        availability_confidence="date_only_conservative_end_of_source_day",
        retrieved_field="retrieved_at",
        revision_policy="provider_history_may_revise",
        corporate_action_policy="not_applicable",
    ),
    "cboe_options_chain_v1": SourceSpec(
        source_id="cboe_options_chain_v1",
        provider="openbb",
        adapter="lake.sources.openbb_global.OpenBBGlobalProvider",
        endpoint="openbb.derivatives.options.chains(provider=cboe)",
        owner="data-infrastructure",
        admission_status="planned",
        allowed_use="research_only",
        license_status="pending",
        license_checked_at="pending",
        storage_restriction="data_lake_only_no_redistribution",
        api_key_env="",
        datasets=("derivatives_daily",),
        allowlist=("SPY",),
        dataset_allowlists=(("derivatives_daily", ("SPY",)),),
        calendar="CBOE",
        timezone="America/New_York",
        currency="USD",
        units="option_contract_chain",
        raw_schema_version="openbb-cboe-options-v1",
        canonical_schema_version="global-options-v1",
        primary_key_policy="contract_symbol_eod_date",
        dedupe_policy="identical_key_rows_dedup_conflicts_reject_batch",
        observed_field="eod_date",
        availability_field="available_at",
        availability_confidence="unverified_requested_date_ignored",
        retrieved_field="retrieved_at",
        revision_policy="unknown",
        corporate_action_policy="contract_lifecycle_required",
    ),
}


def get_dataset_spec(dataset_id: str) -> DatasetSpec:
    try:
        return DATASET_REGISTRY[dataset_id]
    except KeyError as exc:
        raise KeyError(f"unknown global dataset: {dataset_id}") from exc


def get_source_spec(source_id: str) -> SourceSpec:
    try:
        return SOURCE_REGISTRY[source_id]
    except KeyError as exc:
        raise KeyError(f"unknown global source: {source_id}") from exc


def get_source_for_dataset(dataset_id: str, *, source_id: str | None = None) -> SourceSpec:
    if source_id:
        source = get_source_spec(source_id)
        if dataset_id not in source.datasets:
            raise ValueError(f"{source_id} is not admitted for {dataset_id}")
        return source
    candidates = [source for source in SOURCE_REGISTRY.values() if dataset_id in source.datasets]
    if not candidates:
        raise KeyError(f"no source admission record for global dataset: {dataset_id}")
    return candidates[0]


def get_sources_for_dataset(dataset_id: str) -> tuple[SourceSpec, ...]:
    """Return every registered source that can serve a dataset."""
    candidates = tuple(source for source in SOURCE_REGISTRY.values() if dataset_id in source.datasets)
    if not candidates:
        raise KeyError(f"no source admission record for global dataset: {dataset_id}")
    return candidates


_SOURCE_ADMISSION_OVERRIDE_FIELDS = {
    "admission_status",
    "license_status",
    "license_checked_at",
    "allowed_use",
}


def apply_source_admission(source: SourceSpec, override: Mapping[str, str] | None = None) -> SourceSpec:
    """Apply an explicit settings approval without mutating the source registry."""
    if not override:
        return source
    unknown = sorted(set(override) - _SOURCE_ADMISSION_OVERRIDE_FIELDS)
    if unknown:
        raise ValueError(f"unsupported source admission override fields: {','.join(unknown)}")
    candidate = replace(source, **dict(override))
    validate_source_registry({candidate.source_id: candidate})
    return candidate


def validate_dataset_registry(registry: dict[str, DatasetSpec] | None = None) -> None:
    registry = registry or DATASET_REGISTRY
    required_fields = (
        "asset_class",
        "provider",
        "frequency",
        "calendar",
        "timezone",
        "currency",
        "pit_policy",
    )
    for key, spec in registry.items():
        if key != spec.dataset_id:
            raise ValueError(f"registry key mismatch: {key} != {spec.dataset_id}")
        missing = [field for field in required_fields if not getattr(spec, field)]
        if missing:
            raise ValueError(f"{key} missing catalog fields: {','.join(missing)}")


def validate_source_registry(registry: dict[str, SourceSpec] | None = None) -> None:
    registry = registry or SOURCE_REGISTRY
    required_fields = (
        "provider",
        "adapter",
        "endpoint",
        "owner",
        "admission_status",
        "allowed_use",
        "license_status",
        "license_checked_at",
        "storage_restriction",
        "datasets",
        "allowlist",
        "dataset_allowlists",
        "calendar",
        "timezone",
        "currency",
        "units",
        "raw_schema_version",
        "canonical_schema_version",
        "primary_key_policy",
        "dedupe_policy",
        "observed_field",
        "availability_field",
        "availability_confidence",
        "retrieved_field",
        "revision_policy",
        "corporate_action_policy",
    )
    for key, source in registry.items():
        if key != source.source_id:
            raise ValueError(f"source registry key mismatch: {key} != {source.source_id}")
        missing = [field for field in required_fields if not getattr(source, field)]
        if missing:
            raise ValueError(f"{key} missing source admission fields: {','.join(missing)}")
        if source.allowed_use not in {"research_only", "production_candidate", "prohibited"}:
            raise ValueError(f"{key} has invalid allowed_use: {source.allowed_use}")
        if source.availability_field != "available_at":
            raise ValueError(f"{key} availability_field must be available_at")
        if not 0.0 <= source.max_quarantine_ratio < 1.0:
            raise ValueError(f"{key} has invalid max_quarantine_ratio")
        unknown = sorted(set(source.datasets) - set(DATASET_REGISTRY))
        if unknown:
            raise ValueError(f"{key} declares unknown datasets: {','.join(unknown)}")
        declared = {dataset for dataset, _ in source.dataset_allowlists}
        if declared != set(source.datasets):
            raise ValueError(f"{key} dataset_allowlists do not match admitted datasets")
        if not all(values for _, values in source.dataset_allowlists):
            raise ValueError(f"{key} has empty dataset allowlist")
