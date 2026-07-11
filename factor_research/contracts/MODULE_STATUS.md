# MODULE_STATUS

Status: ONLINE

Role: Data transfer objects and view schemas between services, API, and Web.

Keep because: it prevents HTTP routers, services, and UI-facing payloads from inventing separate shapes.

Boundary:
- DTOs only.
- Must not depend on data, engine, strategy, factory, workflow, services, or API logic.
- Domain truth remains in the canonical engine, registry, and workflow modules.
