"""Micro-benchmark to measure the time saved by the shared factor panel optimization in the validation pipeline."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from factory.autoresearch import CandidateRepository, ast_to_hypothesis
from factory.autoresearch.pipeline import run_validation_pipeline
from services.actions.autoresearch import _load_validation_data


def run_benchmark():
    # 1. Load data
    print("Loading price and validation data...")
    close, volume, amount, forward_ret = _load_validation_data("2018-01-01")
    vintage_id = "benchmark_vintage"

    # 2. Retrieve a candidate from repository
    repository = CandidateRepository()
    candidates = list(repository.all())
    if not candidates:
        print("Error: No candidates in repository to benchmark.")
        return

    # Let's find a candidate that has a linear combo with some complexity
    cand = None
    for c in candidates:
        if c.ast.get("type") == "linear_combo" and len(c.ast.get("terms", [])) >= 2:
            cand = c
            break
    if not cand:
        cand = candidates[0]

    print(f"\nBenchmarking Candidate: {cand.fingerprint}")
    print(f"AST: {cand.ast}")

    # 3. Measure time under optimized pipeline (with cached factor)
    t0 = time.time()
    res = run_validation_pipeline(
        cand,
        close=close,
        volume=volume,
        amount=amount,
        forward_ret=forward_ret,
        vintage_id=vintage_id,
        max_stage="l3",
    )
    t_opt = time.time() - t0
    print(f"Optimized Pipeline Execution Time: {t_opt:.2f} seconds")
    print(f"Result Status: {res.status}, Decision: {res.decision}")


if __name__ == "__main__":
    run_benchmark()
