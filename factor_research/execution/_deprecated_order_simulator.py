"""Order Execution Simulator —— **DEPRECATED 孤儿脚手架，禁止接入回测/生产**。

R-ARCH-005：本模块未接入 canonical `core.engine.BacktestEngine`，复活前必须先在
`DECISIONS.md` 立 ADR 说明原因/风险/迁移计划，并补真实结算逻辑 + 测试。

据实说明它**真正做什么**（修正旧 docstring 的撒谎）：
``simulate_execution`` 是一个**单步、无状态的拒单过滤器**——对每条订单按当日
封板/停牌/坏价做"成交 or 拒单"判定，并对成交腿加一个 ``slip_bps`` 滑点估计。

它**没有**实现旧 docstring 宣称的东西，依赖它的人会被误导：
* ✗ **无 T+1 结算**：不区分买卖日，无 settlement 状态机，不阻当日卖出。
* ✗ **无"顺延"**：封板/停牌只产 rejection，不把订单顺延到下一可成交日，不累计顺延损失
  （清单 B 的核心 gap，见 `回测执行现实核对清单.md`）。
* ✗ **无退市归零清算 / 一字板全天封板识别 / partial fill rate**。

唯一仍受测的契约 = ``tests/test_execution_reality.py::
TestExecutionRealityGaps``（钉死"只拒单、不顺延、不在 canonical 路径上"）。
"""
from __future__ import annotations

import warnings

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

class OrderSimulator:
    def __init__(self, slip_bps: float = 15.0):
        warnings.warn(
            "OrderSimulator 已 DEPRECATED(R-ARCH-005):单步拒单过滤器,无 T+1/无顺延,"
            "未接入 canonical 引擎。复活需先立 ADR。勿据其 docstring 接入回测。",
            DeprecationWarning,
            stacklevel=2,
        )
        self.slip_bps = slip_bps

    def simulate_execution(
        self,
        orders: pd.Series,                     # Target weights or shares to trade
        prices: pd.Series,                     # Close price
        limit_ups: pd.Series,                  # Limit up prices
        limit_downs: pd.Series,                # Limit down prices
        suspended: pd.Series                   # Boolean flag for suspensions
    ) -> Tuple[pd.Series, pd.Series, List[Dict[str, Any]]]:
        """Simulate order execution under A-share market constraints.

        Returns
        -------
        filled_trades : pd.Series
            Actual traded shares/weights.
        slippage : pd.Series
            Traded slippage in amount.
        rejections : list of dict
            Details about rejected or failed trades.
        """
        filled = pd.Series(0.0, index=orders.index)
        slippage = pd.Series(0.0, index=orders.index)
        rejections = []

        for asset, size in orders.items():
            if abs(size) < 1e-6:
                continue

            # Check suspension
            is_susp = suspended.get(asset, False)
            if is_susp:
                rejections.append({
                    "asset": asset,
                    "reason": "Suspended / Halted",
                    "size": size
                })
                continue

            price = prices.get(asset, np.nan)
            if np.isnan(price) or price <= 0:
                rejections.append({
                    "asset": asset,
                    "reason": "Invalid Price",
                    "size": size
                })
                continue

            # Check Limit Up/Down
            limit_up = limit_ups.get(asset, price * 1.1)
            limit_down = limit_downs.get(asset, price * 0.9)

            # Buy order is blocked if stock is at limit-up
            if size > 0 and price >= limit_up - 0.01:
                rejections.append({
                    "asset": asset,
                    "reason": "Limit Up (Buy Blocked)",
                    "size": size
                })
                continue

            # Sell order is blocked if stock is at limit-down
            if size < 0 and price <= limit_down + 0.01:
                rejections.append({
                    "asset": asset,
                    "reason": "Limit Down (Sell Blocked)",
                    "size": size
                })
                continue

            # Filled trade
            filled[asset] = size
            slippage[asset] = abs(size) * price * (self.slip_bps / 10000.0)

        return filled, slippage, rejections
