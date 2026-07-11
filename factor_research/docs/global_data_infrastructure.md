# Global Data Infrastructure

This layer extends the A-share data lake with optional global multi-asset data.
It does not replace the canonical A-share lake, production registry, holdout
rules, or `core.engine.BacktestEngine`.

## Provider Policy

- OpenBB is an optional provider adapter, not a hosted data entitlement.
- The repository must import, test, and run without `openbb` installed.
- Missing packages or missing API keys are recorded as source status, not hidden
  behind silent fallbacks.
- New providers should be added beside the OpenBB adapter, not by changing lake
  loader semantics.

## Storage

- Raw provider snapshots live under `data_lake/global_raw/<source>/<dataset>/<ingest_id>/`.
- Dataset parquet files live under `data_lake/global/`.
- Bad row-level records live under `data_lake/global_quarantine/` with their rejection reason.
- The manifest lives at `data_lake/global_manifest.json`.
- Writes must follow `raw snapshot -> normalizer -> validator/quarantine -> canonical writer`.
  `write_global_dataset()` intentionally rejects raw DataFrames; scripts and workflows
  must not direct-write protected global lake paths.
- Canonical rows retain `source_id`, `dataset_id`, `ingest_id`, `retrieved_at`,
  `observed_at`, `available_at`, schema version and currency provenance. Each manifest
  entry records coverage, watermark, quality status, quarantine count, hashes and the
  last good ingest id.

## Source Admission

`lake.global_catalog.SOURCE_REGISTRY` records provider ownership, entitlement state,
allowed use, allowlist, unit/calendar/timezone contract, canonical key policy, revision
policy and PIT confidence. A planned or unlicensed source produces
`source_not_admitted`, not a fallback provider request.

The initial records are deliberately not enabled:

- `alfred_macro_v1`: FRED/ALFRED macro and rates, `research_only`. It requires
  `FRED_API_KEY`. The API returns a real-time vintage date rather than a verified
  intraday publication timestamp, so the adapter converts that date to the end of the
  source day in `America/Chicago`. This is conservative and can delay a signal; it is
  not an assertion of the exact release time.
- `global_etf_price_v1`: global ETF proxy allowlist, `research_only`. OpenBB remains
  an optional probe/provider route, but no ETF source is admitted until it supplies
  exchange, session-close, currency and corporate-action semantics required by the
  canonical schema.

An approved source may be enabled only after its license/entitlement and PIT metadata
are reviewed. Data health exposes `admission_status`, `license_status`, allowed use,
availability confidence, last-good ingest and quarantine count; none of these states
mean that the data is tradable.

Approval is a local configuration decision, not an implicit package install. For example,
after documenting the review, an operator may add the following to their untracked
configuration override:

```yaml
global_data:
  enabled: true
  datasets: [macro_daily, macro_monthly, rates_daily]
  api_key_envs: {alfred: FRED_API_KEY}
  source_admissions:
    alfred_macro_v1:
      admission_status: approved
      license_status: approved
      license_checked_at: "YYYY-MM-DD"
```

The API key remains in the `FRED_API_KEY` environment variable, never in YAML. An
invalid approval field is rejected rather than silently changing a source record.

## Cleaning And PIT

- Macro/revision records use `(series_id, observation_date, vintage_start)` as the
  canonical key. `load_global_macro()` requires a caller-supplied `as_of_date` cutoff
  and joins only values with `available_at <= as_of`. It no longer applies fixed M+2
  when true availability metadata exists.
- Price records use `(symbol, exchange, session_date, adjustment_version)`. They must
  pass positive-price, OHLC ordering, non-negative volume, timezone and duplicate-key
  checks. The normalizer splits raw and adjusted closes; `load_global_price_panel()`
  requires `adjustment_basis="raw"` or `"adjusted"`.
- Schema/key/PIT/unit/OHLC failures reject a batch. Small row-level failures can be
  quarantined only below the source threshold. A rejected, empty or partial response
  never replaces the previous canonical batch.

## PIT Semantics

- Daily market data is visible only after the source market close.
- Macro and rate observations are visible only after their row-level `available_at`.
  `load_global_macro()` requires an explicit as-of cutoff and never infers visibility
  from the observation date. The old M+2 calendar lag remains a legacy safety rule for
  sources without availability metadata; those sources are rejected from this global
  canonical layer.
- News and regulatory events are visible only at `published_at` or `accepted_at`.

## Production Semantics

`settings.global_data.enabled` defaults to false and `required` defaults to
false.  Scheduled daily update treats global data as auxiliary unless
`required=true`; auxiliary failures can produce `partial_ok` but cannot block the
existing A-share signal path.

`scheduled_daily_update` invokes `--all-enabled`, which now respects the disabled
default and configured dataset list. It does not enumerate the catalog merely because
the scheduler ran.

## Operations

```bash
# Check an admitted source/provider without fetching.
python3 scripts/data/update_global_data.py --dataset macro_daily --source alfred_macro_v1 --probe

# Fetch, snapshot, normalize, validate and merge only after source admission.
python3 scripts/data/update_global_data.py --dataset macro_daily --source alfred_macro_v1 --provider-mode alfred --from-watermark

# Re-run normalizer/validator from an immutable raw snapshot.
python3 scripts/data/update_global_data.py --dataset etf_daily --source global_etf_price_v1 --replay-ingest <ingest_id>

# Validate a fetched/replayed batch without writing canonical data or manifest status.
python3 scripts/data/update_global_data.py --dataset macro_daily --source alfred_macro_v1 --validate-only
```
