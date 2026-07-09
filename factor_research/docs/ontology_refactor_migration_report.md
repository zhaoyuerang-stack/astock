# Ontology Refactor Migration Report

## Scope

This migration introduced canonical names for the highest-confusion ontology terms while preserving backward-compatible wrappers.

## Canonical Entrypoints Added

- `engine.factor_composer`
- `engine.signal_factory.factor_to_signal`
- `portfolio.portfolio_composer`
- `factors.alpha.transforms.zscore_cross_section`
- `engine.neutralize.zscore_series`
- `policy.candidate_filters.loser_reversal_filter`
- `factors.illiquidity_components.salience_covariance_score`
- `factors.small_cap.small_cap_exposure_signal`

## Compatibility Entrypoints Retained

- `engine.composer`
- `engine.portfolio.to_signal`
- `portfolio.composer`
- `factors.alpha.transforms.zscore`
- `engine.neutralize.zscore`
- `factors.veto.loser_veto_reversal`
- `factors.veto.salience_covariance_veto`
- `factors.small_cap.small_cap_timing`

## Semantics Preserved

- No strategy formula changed.
- No registry status or evidence changed.
- No cost model changed.
- No `shift(1)`, T+1, rebalance frequency, universe filter, or veto refill behavior changed.

## Verification

- `python3 tests/test_naming_taxonomy.py`
- `python3 tests/test_factor_composer_taxonomy.py`
- `python3 tests/test_signal_factory.py`
- `python3 tests/test_factor_normalization_axis.py`
- `python3 tests/test_veto_filter.py`
- `python3 tests/test_timing_taxonomy.py`
- `python3 scripts/ci/check_naming_taxonomy.py`
- `python3 scripts/ci/check_layer_deps.py`
- `bash scripts/test_all.sh`

## Deferred Work

- Rename `latest_signal` to `latest_decision` only after production/Web consumers are mapped.
- Migrate historical research scripts opportunistically; do not churn archived or scratch files.
- Remove compatibility wrappers only after one release cycle and a clean `rg` audit.
