# MODULE_STATUS

Status: TEMP_ONLY

Role: Temporary experiments, probes, drafts, and local one-off outputs.

Keep because: research needs a sandbox, but it must stay outside canonical evidence paths.

Boundary:
- No formal code may depend on `scratch/`.
- No registry, production, or report claim should rely solely on scratch output.
- Scratch helpers must derive the active checkout from `__file__`; never pin a
  developer path such as `/Users/...`, which can redirect a worktree run into
  the main checkout.
- Registry writes must use `strategy_registry` canonical APIs. Historical
  one-off registration scripts that cannot satisfy the current workflow and
  Nine-Gate evidence contract must fail closed and name the migration path.
- Clean or archive useful artifacts once they become part of a formal workflow.
