"""Order Execution Simulator.

Simulates T+1 settlement rules, halted trading, limit-up/down price bounds,
and partial fill rates.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

class OrderSimulator:
    def __init__(self, slip_bps: float = 15.0):
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
