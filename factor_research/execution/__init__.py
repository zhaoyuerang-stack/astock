"""Execution, TCA, and Compliance module exports."""
from __future__ import annotations

from execution.order_simulator import OrderSimulator
from execution.broker_adapter import BrokerAdapter
from execution.algo_router import AlgoRouter
from execution.tca import TransactionCostAnalyzer
from execution.kill_switch import KillSwitch
from execution.pre_trade_check import PreTradeRiskGate
from execution.post_trade_audit import PostTradeAuditor

__all__ = [
    "OrderSimulator",
    "BrokerAdapter",
    "AlgoRouter",
    "TransactionCostAnalyzer",
    "KillSwitch",
    "PreTradeRiskGate",
    "PostTradeAuditor",
]
