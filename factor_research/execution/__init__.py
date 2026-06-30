"""Execution, TCA, and Compliance module exports."""
from __future__ import annotations

# OrderSimulator 已 DEPRECATED(R-ARCH-005):路径标记 _deprecated_、孤儿+撒谎 docstring 已据实改,
# 不再从包级再导出,避免 `from execution import OrderSimulator` 误导接入。需用须显式
# `from execution._deprecated_order_simulator import OrderSimulator`(仅 deprecation 契约测试可用)。
from execution.broker_adapter import BrokerAdapter
from execution.algo_router import AlgoRouter
from execution.tca import TransactionCostAnalyzer
from execution.kill_switch import KillSwitch
from execution.pre_trade_check import PreTradeRiskGate
from execution.post_trade_audit import PostTradeAuditor

__all__ = [
    "BrokerAdapter",
    "AlgoRouter",
    "TransactionCostAnalyzer",
    "KillSwitch",
    "PreTradeRiskGate",
    "PostTradeAuditor",
]
