# MODULE_STATUS

Status: ONLINE_SUPPORT

Role: Low-level metrics, factor analysis, neutralization, composition, and portfolio utility helpers.

Keep because: many canonical research and reporting paths still depend on these stable utilities.

Boundary:
- Must stay below `factors`, `strategies`, `factory`, `workflow`, and production layers.
- Should not become a second backtest engine.
- Naming should be clarified during the ontology-driven refactor, especially `composer`, `portfolio`, and `to_signal`.
