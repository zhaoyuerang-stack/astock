# MODULE_STATUS

Status: ONLINE_GUARDRAILS

Role: Unit, integration, regression, governance, and architecture tests.

Keep because: tests are the main defense against silent research口径 drift.

Boundary:
- Tests may import broadly to validate behavior.
- Do not treat test fixtures as production behavior.
- New refactors should add characterization tests before moving semantics.
