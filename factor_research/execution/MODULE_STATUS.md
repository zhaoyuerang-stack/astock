# MODULE_STATUS

Status: ARCHIVE_OR_REHOME

Role: Broker adapter, order simulation, algorithm routing, TCA, pre/post-trade checks, and kill switch prototypes.

Current issue: true account automation is explicitly out of scope; production currently emits signals and paper-trading instructions, not broker orders.

Decision:
- Do not present this as an active live execution subsystem.
- Rehome useful simulation/TCA pieces into `portfolio/paper_engine`, `core.engine`, or governance reports if they are actually used.
- Archive broker and routing prototypes unless a real execution project is approved.
