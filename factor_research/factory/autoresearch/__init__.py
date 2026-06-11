"""Controlled Auto Factor Research Engine.

Agents may propose JSON AST candidates; this package validates, scores, logs,
and routes them to human review without touching LIVE strategy registry.
"""
from .complexity import compute_complexity
from .decision import decide_candidate
from .engine import evaluate_lite
from .fingerprint import fingerprint_ast
from .generator import generate_seed_candidates
from .models import (
    Candidate,
    CandidateDecision,
    CandidateEvaluationResult,
    CandidateStatus,
    ComplexityReport,
    LeakageReport,
    RedundancyReport,
)
from .pipeline import ast_to_hypothesis, run_validation_pipeline
from .redundancy import factor_redundancy_score
from .repositories import CandidateRepository, ExperimentLog, ReviewQueue
from .validator import DSLValidationError, validate_candidate_ast

__all__ = [
    "Candidate",
    "CandidateDecision",
    "CandidateEvaluationResult",
    "CandidateRepository",
    "CandidateStatus",
    "ComplexityReport",
    "DSLValidationError",
    "ExperimentLog",
    "LeakageReport",
    "RedundancyReport",
    "ReviewQueue",
    "ast_to_hypothesis",
    "compute_complexity",
    "decide_candidate",
    "evaluate_lite",
    "factor_redundancy_score",
    "fingerprint_ast",
    "generate_seed_candidates",
    "run_validation_pipeline",
    "validate_candidate_ast",
]
