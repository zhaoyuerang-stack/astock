# MODULE_STATUS

Status: MIXED_ENTRYPOINTS

Role: CI guards, data jobs, ops jobs, repair utilities, and research scripts.

Keep because: the project relies on explicit scripts for validation, data updates, maintenance, and investigations.

Boundary:
- `scripts/ci`: authoritative guards.
- `scripts/data`: controlled data writers.
- `scripts/ops`: production/maintenance orchestration.
- `scripts/research`: exploratory or report-generation code; not production authority.
