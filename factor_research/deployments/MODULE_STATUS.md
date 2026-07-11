# MODULE_STATUS

Status: ONLINE_CONFIG

Role: Deployment manifests, especially `production.json`.

Keep because: production readiness and `run_daily.py` need an explicit deployment declaration, even when status is paused or fail-closed.

Boundary:
- Configuration artifact, not Python library.
- Active declarations must be mechanically loadable by runtime deployment checks.
- Do not use deployment manifests to bypass registry or 9-Gate governance.
