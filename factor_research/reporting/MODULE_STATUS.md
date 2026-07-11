# MODULE_STATUS

Status: ARCHIVE_OR_REHOME

Role: Standalone attribution, gross-to-net, benchmark, drawdown, exposure, turnover, and audit-pack helpers.

Current issue: useful reporting concepts exist, but the active product reads mostly through `services/read` and generated `reports/`.

Decision:
- Do not keep expanding as an independent top-level subsystem.
- Rehome used report builders into `services/read`, `governance`, or explicit report-generation scripts.
- Archive unused GIPS-style helpers if no canonical consumer is created.
