"""M4 Strategy: High-Quality Momentum Hedged.

Long top N highest smooth momentum stocks from a high-quality fundamental universe, hedged with CSI 800 equal-weighted index.
"""
from dataclasses import dataclass, asdict

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from core.hedged_portfolio import HedgedReturnPolicy, equal_weight_universe_returns
from factors.hq_momentum import build_hq_momentum_factor
from strategies.small_cap import build_rebalance_weights

@dataclass(frozen=True)
class StrategyConfig:
    family: str = "hq-momentum-hedged"
    version: str = "v1.0"
    start: str = "2012-01-01"
    universe_size: int = 800
    lookback: int = 60
    q_filter_threshold: float = 0.60  # Only keep top 40% quality (1 - threshold)
    top_n: int = 25
    rebalance_days: int = 20
    leverage: float = 1.0
    hedge_cost_annual: float = 0.015

    def to_dict(self):
        return asdict(self)

def run_hq_momentum_strategy(config=StrategyConfig()):
    """Runs the complete High-Quality Momentum Hedged strategy."""
    from factors.large_cap import load_clean_panels_with_growth
    
    # Load data
    panels = load_clean_panels_with_growth()
    close = panels["close"]
    volume = panels["amount"] * 0.0
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_close)

    # Build factor
    comp_factor, univ = build_hq_momentum_factor(
        panels, 
        universe_size=config.universe_size, 
        lookback=config.lookback, 
        q_filter_threshold=config.q_filter_threshold
    )

    # Scheduled weights
    scheduled = build_rebalance_weights(comp_factor, close, config.top_n, config.rebalance_days)
    
    # Engine configuration
    engine_config = BacktestConfig(
        start="2010-01-01",  # Warm-up from 2010
        # R-COST-001: hedge borrow cost does not replace long-leg turnover
        # costs.  Use the canonical A-share cost model for the stock book.
        cost=CostModel(),
        leverage=config.leverage,
    )
    engine = BacktestEngine(prices=prices, config=engine_config)
    long_signal = Signal(weights=scheduled, timing=None)
    res_long = engine.run(long_signal)

    # Canonical hedged-return policy, shared verbatim with Nine-Gate replays.
    policy = HedgedReturnPolicy(
        benchmark_returns=equal_weight_universe_returns(close, univ),
        hedge_cost_annual=config.hedge_cost_annual,
        warmup_start="2010-01-01",
    )
    hedged = policy.apply(res_long, statistics_start=config.start)

    return {
        "returns": hedged.result.returns,
        "long_returns": hedged.long_returns,
        "bench_returns": hedged.benchmark_returns,
        "scheduled_weights": scheduled,
        "factor": comp_factor,
        "close": close,
        "volume": volume,
        "amount": amount,
        "engine_result": res_long,
        "portfolio_result": hedged.result,
        "portfolio_policy": policy,
    }

def latest_signal(config=StrategyConfig()):
    """Returns the latest signal and holdings for live trading."""
    result = run_hq_momentum_strategy(config)
    
    close = result["close"]
    comp_factor = result["factor"]
    
    last = close.index[-1]
    f = comp_factor.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(config.top_n).index.tolist()
    
    return {
        "date": last,
        "in_market": True,
        "holdings": holdings,
        "result": result,
    }
