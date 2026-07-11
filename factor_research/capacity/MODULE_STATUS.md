# MODULE_STATUS

Status: ARCHIVE_OR_REHOME

Role: Standalone capacity, participation, crowding, decay, and live-vs-backtest helpers.

Current issue: useful concepts exist here, but the production and 9-Gate paths mostly consume capacity logic elsewhere. As a top-level module it can overstate how integrated capacity governance is.

Decision:
- Do not expand as an independent top-level subsystem.
- Either rehome needed functions into `core.analysis`, `governance`, or `portfolio`, or archive unused pieces.
- New capacity checks should be wired into canonical gates before being described as active controls.
