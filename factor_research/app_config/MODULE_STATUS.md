# MODULE_STATUS

Status: ONLINE

Role: Unified application configuration.

Keep because: runtime behavior, strategy defaults, holdout settings, model settings, and cost-related configuration must have a single controlled entrypoint.

Boundary:
- Configuration belongs here or in explicitly documented deployment manifests.
- Business logic must not hard-code values that belong in settings.
- Tests may use local fixtures but must not mutate canonical settings silently.
