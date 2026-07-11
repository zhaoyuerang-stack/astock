# MODULE_STATUS

Status: ONLINE

Role: Canonical strategy construction and latest decision logic for registered strategy families.

Keep because: production and research runners need stable strategy implementations.

Boundary:
- May consume factors and core engine.
- Must not depend on factory, workflow, research scripts, services, or API.
- Strategy code must not bypass registry or production readiness.
