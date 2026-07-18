"""Emergency Kill Switch.

Halts all trading and closes positions immediately upon breach.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List

class KillSwitch:
    """Institutional Kill Switch / Circuit Breaker."""
    def __init__(self, max_drawdown_limit: float = 0.15, max_leverage_limit: float = 1.5):
        self.max_drawdown_limit = max_drawdown_limit
        self.max_leverage_limit = max_leverage_limit
        self.armed = True
        self.triggered = False
        self.trigger_reason = ""
        self.logger = logging.getLogger("KillSwitch")

    def monitor_risk(self, current_drawdown: float, current_leverage: float) -> bool:
        """Monitor risk and trigger the switch if limits are exceeded."""
        if not self.armed or self.triggered:
            return self.triggered

        if abs(current_drawdown) > self.max_drawdown_limit:
            self.trigger(f"Drawdown {current_drawdown:.2%} exceeded limit {self.max_drawdown_limit:.2%}")
        elif current_leverage > self.max_leverage_limit:
            self.trigger(f"Leverage {current_leverage:.2f} exceeded limit {self.max_leverage_limit:.2f}")

        return self.triggered

    def trigger(self, reason: str):
        self.triggered = True
        self.trigger_reason = reason
        self.logger.critical(f"!!! KILL SWITCH TRIGGERED !!! Reason: {reason}")
        self.execute_liquidation()

    def execute_liquidation(self) -> List[Dict[str, Any]]:
        """Emergency flatten portfolio."""
        self.logger.info("Executing emergency portfolio liquidation...")
        # Returns orders to sell all current stock positions
        return [{"symbol": "ALL", "action": "LIQUIDATE_IMMEDIATELY"}]

    def disarm(self):
        self.armed = False
        self.logger.info("Kill switch has been disarmed.")

    def rearm(self):
        self.armed = True
        self.triggered = False
        self.trigger_reason = ""
        self.logger.info("Kill switch has been re-armed.")
