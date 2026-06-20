"""Transaction Cost Analysis (TCA).

Evaluates slippage, commissions, stamp duties, and market impact relative to benchmarks.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, Any

class TransactionCostAnalyzer:
    def __init__(self, commission_rate: float = 0.000065, tax_rate: float = 0.0005):
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate

    def analyze_execution(
        self,
        symbol: str,
        direction: str,                     # BUY | SELL
        quantity: int,
        execution_price: float,
        benchmark_price: float,             # arrival price
        market_adv: float
    ) -> Dict[str, Any]:
        """Compute slippage, commission, stamp duty, and market impact of the execution."""
        turnover = quantity * execution_price

        # Explicit costs
        commission = turnover * self.commission_rate
        tax = turnover * self.tax_rate if direction == "SELL" else 0.0

        # Slippage in bps: execution vs arrival price
        if benchmark_price > 0:
            price_diff = execution_price - benchmark_price
            slippage_bps = (price_diff / benchmark_price) * 10000.0 if direction == "BUY" else (-price_diff / benchmark_price) * 10000.0
        else:
            slippage_bps = 0.0

        # Estimate market impact using square-root participation model
        part_rate = quantity / market_adv if market_adv > 0 else 0.0
        estimated_impact_bps = 50.0 * np.sqrt(part_rate) if part_rate > 0 else 0.0

        total_cost_cny = commission + tax + (slippage_bps / 10000.0) * turnover

        return {
            "symbol": symbol,
            "direction": direction,
            "quantity": quantity,
            "execution_price": execution_price,
            "benchmark_price": benchmark_price,
            "slippage_bps": slippage_bps,
            "commission": commission,
            "tax": tax,
            "market_impact_bps": estimated_impact_bps,
            "total_cost_cny": total_cost_cny,
            "total_cost_bps": (total_cost_cny / (turnover if turnover > 0 else 1.0)) * 10000.0
        }
