# MODULE_STATUS: execution
Status: ARCHIVE_OR_REHOME
Role: Institutional execution stack (order_simulator, tca, kill_switch) with no live caller.
Keep because: Only a single test imports it; not wired into production/workflow.

Boundary:
- Do not treat as live; rehome or archive only via human-approved plan.
