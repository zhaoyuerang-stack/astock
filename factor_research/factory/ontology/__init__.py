"""工厂本体 — Hypothesis / Experiment / Insight 三元组。

Hypothesis 是原料（因子假设），Experiment 是测试，Insight 是产生的可复用知识。
旧 factory/*.py 是 NSGA-II 老框架，Phase 6 才迁移。
"""
from .hypothesis import (
    EconomicThesis,
    Hypothesis,
    HypothesisStatus,
)
from .experiment import (
    Decision,
    Experiment,
    ExperimentProtocol,
    ExperimentResult,
)
from .insight import Insight, InsightKind
from .invariants import (
    InvariantViolation,
    check_f1_economic_thesis,
    check_f2_cheap_first,
)
from .report_logic import (
    TransmissionNode,
    LogicalChain,
    TransmissionNodeCategory,
    NodeChange,
)

__all__ = [
    "EconomicThesis",
    "Hypothesis",
    "HypothesisStatus",
    "Decision",
    "Experiment",
    "ExperimentProtocol",
    "ExperimentResult",
    "Insight",
    "InsightKind",
    "InvariantViolation",
    "check_f1_economic_thesis",
    "check_f2_cheap_first",
    "TransmissionNode",
    "LogicalChain",
    "TransmissionNodeCategory",
    "NodeChange",
]
