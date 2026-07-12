"""Blocked historical registration helper for illiquidity v3.0/v3.1.

The former script copied hand-entered performance into the registry and marked
v3.1 as ``在册`` without running the current workflow, holdout, or DSR gates.
Replaying it would turn stale historical evidence into a fresh registry write.

Migration path:
  1. Recreate the candidate through ``factory`` / ``workflow.promote``.
  2. Run the canonical Nine-Gate audit on the current data vintage.
  3. Let ``workflow.phase4_register`` call ``strategy_registry.register``.

The old values remain recoverable from git history; they are intentionally not
an executable registration path anymore.
"""


BLOCKED_MESSAGE = (
    "BLOCKED: register_v3.py is a retired one-off that bypasses the current "
    "promotion evidence chain. Recreate and promote the candidate through "
    "workflow.promote; do not copy historical metrics into the registry."
)


def main() -> int:
    print(BLOCKED_MESSAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
