# MODULE_STATUS

Status: ONLINE

Role: FastAPI HTTP routing layer.

Keep because: it exposes product-facing endpoints while keeping business logic in `services.read` and `services.actions`.

Boundary:
- May depend on `services.*` and `contracts.*`.
- Must not directly read or write runtime artifacts such as `data_lake/`, `reports/`, `signals/`, or `paper/`.
- Must not import research or engine internals directly.
