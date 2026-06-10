"""run_backtest —— 包住唯一权威回测路径(照搬 strategy_lake.py 的调用)。

铁律护栏(违反 = 结论作废):
- 回测**只**走 core.engine.BacktestEngine,不在此旁路重算因子/估值。
- 成本固化为 CostModel(买 0.225% / 卖 0.275% / 融资 6.5%),**不可调低**。
- 口径为 data_lake(load_price_panels),绝不用 data_full。

验证:本函数与 strategy_lake.run_backtest 走完全相同的代码路径,故同区间
metrics 必须逐项相等(见 tests/test_services_phase0.py)。
"""
from __future__ import annotations

from contracts.views import BacktestResult

# 成本铁律(与 CLAUDE.md / strategy_lake.py 一致),固定不暴露给调用方调低
_BUY_COST = 0.00225
_SELL_COST = 0.00275
_FINANCING_RATE = 0.065


def run_backtest(
    start: str = "2018-01-01",
    top_n: int = 25,
    rebalance_days: int = 20,
    factor_window: int = 60,
    timing_ma: int = 16,
    leverage: float = 1.25,
    family: str = "small-cap-size",
    version: str = "v2.0",
) -> BacktestResult:
    # 受控接缝:services 有意允许 import 引擎(守卫白名单)
    from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
    from strategies.small_cap import load_price_panels, build_rebalance_weights
    from factors.small_cap import small_cap_factor, small_cap_timing

    close, volume, amount = load_price_panels(start)
    prices = PricePanel(close=close, volume=volume, amount=amount)

    factor = small_cap_factor(amount, window=factor_window)
    timing, _, _ = small_cap_timing(close, amount, ma_window=timing_ma)
    scheduled = build_rebalance_weights(
        factor, close, top_n=top_n, rebalance_days=rebalance_days
    )

    engine = BacktestEngine(
        prices=prices,
        config=BacktestConfig(
            start=start,
            cost=CostModel(
                buy_cost=_BUY_COST, sell_cost=_SELL_COST, financing_rate=_FINANCING_RATE
            ),
            leverage=leverage,
        ),
    )
    signal = Signal(weights=scheduled, timing=timing, family=family, version=version)
    result = engine.run(signal)

    m = result.metrics
    yearly = {int(y): float(r) for y, r in result.yearly_returns.items()}
    return BacktestResult(
        annual=m["annual"], vol=m["vol"], sharpe=m["sharpe"], maxdd=m["maxdd"],
        calmar=m["calmar"], hit=bool(m["hit"]), n=int(m["n"]),
        turnover_annual=float(result.detail["turnover"].mean() * 252),
        cost_annual=float(result.detail["cost"].mean() * 252),
        yearly_returns=yearly,
        n_stocks=int(close.shape[1]), n_days=int(close.shape[0]),
        start=str(close.index[0].date()), end=str(close.index[-1].date()),
        family=family, version=version,
    )
