# MODULE_STATUS

Status: ONLINE

Role: Strategy runners, research catalog, deployment runner, portfolio composition, paper engine, cross-asset legs, and optimization helpers.

Keep because: strategy returns, deployment composition, and paper trading meet here.

Boundary:
- Should consume registry, runtime deployment specs, strategies, and engine results.
- Must not bypass production readiness or registry status.
- Some optimizer and institutional-upgrade helpers may need separate staging labels if not wired into active runners.
