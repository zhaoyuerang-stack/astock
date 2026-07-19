"""Pre-Trade Compliance & Risk Gate.

Performs trade validation checks before routing orders to the broker.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any

class PreTradeRiskGate:
    def __init__(
        self,
        max_single_weight: float = 0.05,
        max_portfolio_leverage: float = 1.25,
        max_adv_participation: float = 0.05
    ):
        self.max_single_weight = max_single_weight
        self.max_portfolio_leverage = max_portfolio_leverage
        self.max_adv_participation = max_adv_participation

    def check_compliance(
        self,
        target_weights: pd.Series,             # Asset -> Target weight
        adv: pd.Series,                        # Asset -> ADV
        stk_limits: Dict[str, Tuple[float, float]], # Asset -> (limit_down, limit_up)
        suspended_stocks: List[str]            # list of suspended assets
    ) -> Tuple[bool, List[Dict[str, Any]], pd.Series]:
        """Validate proposed trades.

        Returns
        -------
        passed : bool
            True if compliant, False otherwise.
        alerts : list of dict
            Specific rule violations found.
        compliant_weights : pd.Series
            Adjusted compliant weight targets.
        """
        passed = True
        alerts = []
        compliant = target_weights.copy()

        # Check total leverage
        total_w = target_weights.sum()
        if total_w > self.max_portfolio_leverage:
            passed = False
            alerts.append({
                "rule": "portfolio_leverage",
                "message": f"Proposed leverage {total_w:.2f} exceeds cap {self.max_portfolio_leverage:.2f}"
            })
            # scale down
            compliant = compliant * (self.max_portfolio_leverage / total_w)

        # Check individual weights
        for asset, weight in compliant.items():
            if weight > self.max_single_weight:
                passed = False
                alerts.append({
                    "rule": "single_stock_weight",
                    "asset": asset,
                    "message": f"Asset {asset} weight {weight:.2%} exceeds cap {self.max_single_weight:.%}"
                })
                compliant[asset] = self.max_single_weight

            # Check suspended
            if asset in suspended_stocks and abs(weight) > 1e-5:
                passed = False
                alerts.append({
                    "rule": "asset_suspended",
                    "asset": asset,
                    "message": f"Cannot trade suspended stock {asset}"
                })
                compliant[asset] = 0.0

        return passed, alerts, compliant
