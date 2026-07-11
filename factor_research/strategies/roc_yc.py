"""ROC (Return on Capital) and YC (Earnings Yield) dual-factor strategy implementation.

Implements Joel Greenblatt's Magic Formula (神奇公式):
Long top N stocks ranked by cross-sectional blend of ROC (proxy: ROE) and YC (proxy: 1/PE).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import pandas as pd
import numpy as np

from core.engine import BacktestConfig, BacktestEngine, CostModel, PricePanel, Signal
from factors.roc_yc import roc_yc_composite_factor, roc_yc_neutralized_factor
from lake.load_lake import load_raw_close
from strategies.small_cap import load_price_panels, build_rebalance_weights, _drop_star


@dataclass(frozen=True)
class StrategyConfig:
    family: str = "roc-yc"
    version: str = "v1.0"
    start: str = "2018-01-01"
    blend_weight: float = 0.5       # Weight on ROC (1 - blend_weight on YC)
    neutralize: bool = False        # Neutralize factor against CNE6 style panels
    hedged: bool = False            # Neutralize Beta by shorting the equal-weight market index
    hedge_cost_annual: float = 0.015  # Annualized transaction fee/slippage cost for hedging
    top_n: int = 25
    rebalance_days: int = 20
    leverage: float = 1.25
    cost: CostModel = CostModel()
    exclude_star: bool = True       # Exclude Star market (688) stocks

    def to_dict(self):
        return asdict(self)


def run_roc_yc_strategy(config: StrategyConfig | None = None) -> dict:
    """Runs the ROC-YC strategy using BacktestEngine."""
    if config is None:
        config = StrategyConfig()

    close, volume, amount = load_price_panels(config.start)
    if config.exclude_star:
        close, volume, amount = _drop_star(close, volume, amount)

    # Reindex raw close to match close shape
    raw = load_raw_close(start=config.start)
    if not raw.empty:
        raw = raw.reindex(index=close.index, columns=close.columns)
        prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw)
    else:
        prices = PricePanel(close=close, volume=volume, amount=amount)

    # Compute blended factor: ROC (ROE) and YC (EP)
    if config.neutralize:
        factor = roc_yc_neutralized_factor(
            close=close,
            amount=amount,
            blend_weight=config.blend_weight,
        )
    else:
        factor = roc_yc_composite_factor(
            close=close,
            blend_weight=config.blend_weight,
        )

    # Generate rebalance target weights
    scheduled = build_rebalance_weights(
        factor=factor,
        close=close,
        top_n=config.top_n,
        rebalance_days=config.rebalance_days,
    )

    # Configure BacktestEngine
    engine_config = BacktestConfig(
        start=config.start,
        cost=CostModel(
            buy_cost=config.cost.buy_cost,
            sell_cost=config.cost.sell_cost,
            financing_rate=config.cost.financing_rate,
        ),
        leverage=config.leverage,
    )
    engine = BacktestEngine(prices=prices, config=engine_config)
    signal = Signal(
        weights=scheduled,
        timing=None,  # No market timing by default
        family=config.family,
        version=config.version,
    )
    result = engine.run(signal)

    returns = result.returns
    if config.hedged:
        # Calculate size-matched CSI 800 equal-weighted benchmark return to prevent benchmark basis mismatch
        # Use raw close if available, fallback to adjusted close
        px_for_size = raw if not raw.empty else close
        cap = amount.rolling(20).mean() * px_for_size
        univ_mask = cap.rank(axis=1, ascending=False) <= 800

        daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        
        # Shift mask by 1 day to avoid look-ahead bias
        univ_shifted = univ_mask.shift(1)
        bench_returns = (daily_ret * univ_shifted).sum(axis=1) / univ_shifted.sum(axis=1).replace(0, np.nan)
        bench_returns = bench_returns.fillna(0.0)

        common_idx = returns.index.intersection(bench_returns.index)
        returns = returns.loc[common_idx]
        bench_returns = bench_returns.loc[common_idx]

        daily_hedge_cost = config.hedge_cost_annual / 252.0
        returns = returns - bench_returns - daily_hedge_cost

        # Update result metrics in-place for down-stream compatibility
        result.returns = returns
        result.detail = pd.DataFrame(
            {"ret": returns, "turnover": result.turnover.loc[common_idx], "cost": result.cost.loc[common_idx]},
            index=common_idx,
        )

    return {
        "close": close,
        "volume": volume,
        "amount": amount,
        "factor": factor,
        "scheduled_weights": scheduled,
        "returns": returns,
        "detail": result.detail,
        "engine_result": result,
    }


def latest_signal(config: StrategyConfig | None = None) -> dict:
    """Returns the latest signal and holdings for live trading."""
    if config is None:
        config = StrategyConfig()

    result = run_roc_yc_strategy(config)
    close = result["close"]
    factor = result["factor"]
    last = close.index[-1]

    f = factor.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(config.top_n).index.tolist()

    return {
        "date": last,
        "in_market": True,
        "holdings": holdings,
        "result": result,
    }
