# MODULE_STATUS

Status: ONLINE_CRITICAL

Role: Data lake loaders, data sources, validators, invariants, fingerprints, and unit normalization.

Keep because: formal research and production signals depend on canonical data access and quality checks.

Boundary:
- Lake code may write/read data-lake artifacts through controlled paths.
- Must not depend on factors, strategies, factory, workflow, services, or API.
- Data quality failures should fail closed rather than silently change research口径.
