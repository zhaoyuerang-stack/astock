# MODULE_STATUS

Status: ONLINE_CRITICAL

Role: Canonical backtest engine, strategy specs, analysis gates, overlays, and risk primitives.

Keep because: `core.engine.BacktestEngine` is the only authority for formal backtests and performance evidence.

Boundary:
- Must remain below strategies, factory, workflow, registry, production, API, and services.
- No imports from strategy-specific or research orchestration layers.
- Cost, T+1, shift, and execution semantics must not be changed for convenience.
