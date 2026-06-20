#!/usr/bin/env python3
"""Bulk promote approved review candidates and L3 pool candidates to strategy registry."""
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from factory.autoresearch import ReviewQueue, CandidateStatus, CandidateRepository
from services.actions.autoresearch import promote_approved_candidate, review_autoresearch_candidate
from workflow.promote import promote_pool_l3, promote_hypothesis


def run_bulk_promotion():
    print("=== Step 1: Loading Review Queue ===")
    review_queue = ReviewQueue()
    repository = CandidateRepository()
    
    # 1. Approve pending items in ReviewQueue
    pending_items = [
        item for item in review_queue.all()
        if item.get("status") == CandidateStatus.PROMOTED_TO_REVIEW.value
    ]
    print(f"Found {len(pending_items)} pending candidates in Review Queue.")
    for item in pending_items:
        fp = item["fingerprint"]
        print(f"Approving pending candidate: {fp}...")
        try:
            review_autoresearch_candidate(
                fingerprint=fp,
                action="approve",
                notes="Approved via bulk promotion script",
                repository=repository,
                review_queue=review_queue
            )
            print(f"  → Approved successfully.")
        except Exception as e:
            print(f"  → Error approving {fp}: {e}")

    # Reload queue after approvals
    review_queue = ReviewQueue()
    approved_items = [
        item for item in review_queue.all()
        if item.get("status") == CandidateStatus.APPROVED.value or item.get("review_action") == "approve"
    ]
    print(f"\nFound {len(approved_items)} approved candidates in Review Queue to promote.")
    
    # Custom promote function wrapper to force-promote (passing force=True)
    def force_promote_fn(hyp, version="v1.0", run_marginal=False):
        return promote_hypothesis(hyp, version=version, run_marginal=run_marginal, force=True)

    # 2. Promote all approved items
    for item in approved_items:
        fp = item["fingerprint"]
        print(f"\nPromoting candidate: {fp}...")
        try:
            res = promote_approved_candidate(
                fingerprint=fp,
                version="v1.0",
                run_marginal=False,
                repository=repository,
                review_queue=review_queue,
                promote_fn=force_promote_fn
            )
            print(f"  → Promotion result: registered={res.registered}, hypothesis={res.hypothesis_name}, detail={res.detail}")
        except Exception as e:
            print(f"  → Error promoting candidate {fp}: {e}")

    # 3. Promote L3_PASSED pool candidates
    print("\n=== Step 2: Promoting L3 Passed Pool Candidates ===")
    try:
        reports = promote_pool_l3(version="v1.0", force=True, run_marginal=False)
        print(f"Promoted {len(reports)} candidates from Hypothesis Pool.")
        for r in reports:
            if r:
                print(f"  → Family={r.family}, registered={r.registered}, detail={r.detail}")
    except Exception as e:
        print(f"Error promoting pool candidates: {e}")

    print("\n=== Step 3: Done ===")


if __name__ == "__main__":
    run_bulk_promotion()
