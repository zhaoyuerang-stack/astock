"""Post-Trade Audit and Reconciliation.

Reconciles broker execution fills against original target trade orders.
"""
from __future__ import annotations

import pandas as pd
from typing import Dict, List, Any

class PostTradeAuditor:
    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []

    def audit_reconciliation(
        self,
        proposed_trades: pd.Series,            # Asset -> target order quantity/shares
        filled_trades: pd.Series,              # Asset -> broker fill quantity/shares
        fill_prices: pd.Series                 # Asset -> avg fill price
    ) -> Dict[str, Any]:
        """Perform reconciliation check of filled quantity vs proposed quantity."""
        unfilled_assets = []
        discrepancies = []
        total_filled_value = 0.0

        for asset, proposed_qty in proposed_trades.items():
            filled_qty = filled_trades.get(asset, 0.0)
            diff = proposed_qty - filled_qty
            price = fill_prices.get(asset, 0.0)
            total_filled_value += filled_qty * price

            if abs(proposed_qty) > 0 and filled_qty == 0:
                unfilled_assets.append(asset)
                discrepancies.append({
                    "asset": asset,
                    "type": "COMPLETELY_UNFILLED",
                    "proposed": proposed_qty,
                    "filled": 0
                })
            elif abs(diff) > 1e-5:
                discrepancies.append({
                    "asset": asset,
                    "type": "PARTIAL_FILL_MISMATCH",
                    "proposed": proposed_qty,
                    "filled": filled_qty,
                    "difference": diff
                })

        audit_entry = {
            "reconciled_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "proposed_count": len(proposed_trades[proposed_trades != 0]),
            "filled_count": len(filled_trades[filled_trades != 0]),
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies,
            "total_filled_value_cny": total_filled_value
        }

        self.audit_log.append(audit_entry)
        return audit_entry
