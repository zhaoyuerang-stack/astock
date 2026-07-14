"""M2 Mother Strategy: Large-cap Growth+Valuation Hedged + Hysteresis Timing.

Implementation of the second mother strategy family.
"""
from dataclasses import dataclass, asdict
from functools import partial

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from core.hedged_portfolio import HedgedReturnPolicy, equal_weight_universe_returns
from factors.large_cap import load_clean_panels_with_growth, build_large_cap_premium_factor, large_cap_timing_hysteresis
from strategies.small_cap import build_rebalance_weights

@dataclass(frozen=True)
class StrategyConfig:
    family: str = "large-cap-growth-hedged"
    version: str = "v1.0"
    start: str = "2010-01-01"
    universe_size: int = 200
    top_n: int = 25
    rebalance_days: int = 40
    leverage: float = 1.0
    ma_window: int = 120
    buffer_size: float = 0.01
    hedge_cost_annual: float = 0.015
    switch_friction: float = 0.0025
    w_cpv_max: float = 0.0  # Weight for adaptive CPV penalty (0.0 for v1.0, 0.5 for v1.1)

    def to_dict(self):
        return asdict(self)

def run_large_cap_strategy(config=StrategyConfig()):
    """Runs the complete Large-cap Growth Hedged strategy.
    
    1. Runs unified engine on growth premium long portfolio.
    2. Subtracts shifted Top 200 equal-weighted index (including 1.5% hedge cost).
    3. Applies hysteresis timing signal on NAV (with 0.25% transition friction).
    4. Slices outputs to config.start (ensuring proper MA warm-up).
    """
    # Load data
    panels = load_clean_panels_with_growth()
    close = panels["close"]
    volume = panels["amount"] * 0.0
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_close)

    # Build factor (with optional adaptive CPV penalty)
    comp_premium, univ = build_large_cap_premium_factor(
        panels, universe_size=config.universe_size, w_cpv_max=config.w_cpv_max
    )

    # Scheduled weights
    scheduled = build_rebalance_weights(comp_premium, close, config.top_n, config.rebalance_days)
    
    # Engine configuration (Always run from 2010-01-01 to warm up MAs)
    engine_config = BacktestConfig(
        start="2010-01-01",
        # R-COST-001: the long stock leg pays the same canonical A-share
        # execution costs as every other formal strategy.  The hedge borrow
        # cost and strategy-level switch friction are charged separately below.
        cost=CostModel(),
        leverage=config.leverage,
    )
    engine = BacktestEngine(prices=prices, config=engine_config)
    long_signal = Signal(weights=scheduled, timing=None)
    res_long = engine.run(long_signal)

    # Canonical hedged-return policy, shared verbatim with Nine-Gate replays.
    # The timing overlay is intentionally applied after neutral NAV is built.
    policy = HedgedReturnPolicy(
        benchmark_returns=equal_weight_universe_returns(close, univ),
        hedge_cost_annual=config.hedge_cost_annual,
        timing_builder=partial(
            large_cap_timing_hysteresis,
            window=config.ma_window,
            buffer=config.buffer_size,
        ),
        switch_friction=config.switch_friction,
        warmup_start="2010-01-01",
    )
    hedged = policy.apply(res_long, statistics_start=config.start)

    return {
        "returns": hedged.result.returns,
        "long_returns": hedged.long_returns,
        "bench_returns": hedged.benchmark_returns,
        "neutral_returns": hedged.neutral_returns,
        "timing": hedged.timing,
        "scheduled_weights": scheduled,
        "factor": comp_premium,
        "close": close,
        "volume": volume,
        "amount": amount,
        "engine_result": res_long,
        "portfolio_result": hedged.result,
        "portfolio_policy": policy,
    }

def latest_signal(config=StrategyConfig()):
    """Returns the latest signal and holdings for live trading."""
    # Run strategy
    result = run_large_cap_strategy(config)
    
    close = result["close"]
    comp_premium = result["factor"]
    
    last = close.index[-1]
    f = comp_premium.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(config.top_n).index.tolist()
    
    # Timing status
    in_market = bool(result["timing"].loc[last])
    
    return {
        "date": last,
        "in_market": in_market,
        "holdings": holdings,
        "result": result,
    }
