"""Closed-world and AST-level tests for the holdout guard."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from factory.autoresearch.islands import run_island_search
from governance.holdout import HoldoutBreach, assert_search_clean
from scripts.ci.check_holdout_compliance import (
    DELEGATED,
    EXEMPT,
    REQUIRED,
    REQUIRED_ENTRYPOINTS,
    discover_selection_paths,
    has_holdout_call,
    is_selection_source,
)


def test_comment_or_string_does_not_satisfy_holdout_guard():
    src = "# assert_search_clean(close.index)\nNOTE = 'validate_on_holdout(x)'\n"
    assert has_holdout_call(src) is False


def test_real_holdout_call_satisfies_guard():
    assert has_holdout_call("assert_search_clean(close.index)") is True


def test_literal_dead_code_does_not_satisfy_guard():
    src = "if False:\n    assert_search_clean(close.index)\n"
    assert has_holdout_call(src) is False


def test_unused_guarded_helper_does_not_satisfy_bound_entrypoint():
    src = """
def unused_guard():
    assert_search_clean(close.index)

def rank_candidates():
    frame = read_parquet("candidates.parquet")
    return frame.nlargest(10, "score")
"""
    # Compatibility query still reports that the file contains a live guard.
    assert has_holdout_call(src) is True
    # Enforcement is entrypoint-bound: the unused helper cannot launder rank_candidates.
    assert has_holdout_call(src, ("rank_candidates",)) is False


def test_called_local_guard_helper_satisfies_bound_entrypoint():
    src = """
def enforce_boundary(index):
    assert_search_clean(index)

def rank_candidates(close):
    enforce_boundary(close.index)
    return close
"""
    assert has_holdout_call(src, ("rank_candidates",)) is True


def test_unrelated_object_method_cannot_launder_unused_local_helper():
    src = """
def enforce_boundary(index):
    assert_search_clean(index)

def rank_candidates(repository):
    repository.enforce_boundary()
    return repository.read_parquet().nlargest(10, "score")
"""
    assert has_holdout_call(src, ("rank_candidates",)) is False


def test_dead_call_to_guarded_helper_does_not_satisfy_bound_entrypoint():
    src = """
def enforce_boundary(index):
    assert_search_clean(index)

def rank_candidates(close):
    if False:
        enforce_boundary(close.index)
    return close
"""
    assert has_holdout_call(src, ("rank_candidates",)) is False


def test_call_after_return_or_short_circuit_is_not_active():
    after_return = """
def rank_candidates(close):
    return close
    assert_search_clean(close.index)
"""
    short_circuit = """
def rank_candidates(close):
    False and assert_search_clean(close.index)
    return close
"""
    assert has_holdout_call(after_return, ("rank_candidates",)) is False
    assert has_holdout_call(short_circuit, ("rank_candidates",)) is False


def test_class_method_entrypoint_can_be_bound_explicitly():
    src = """
class Runner:
    def run(self, close):
        assert_search_clean(close.index)
        return close
"""
    assert has_holdout_call(src, "Runner.run") is True


def test_known_selection_definition_is_discovered():
    assert is_selection_source("def run_island_search(close):\n    return close\n") is True


def test_new_search_loader_is_discovered_by_shape():
    src = "def search_new_factor():\n    close = load_prices()\n    return close\n"
    assert is_selection_source(src) is True


def test_rank_candidates_read_parquet_nlargest_is_discovered():
    src = """
def rank_candidates(path):
    candidates = read_parquet(path)
    return candidates.nlargest(10, "score")
"""
    assert is_selection_source(src) is True


def test_research_and_zscore_substrings_are_not_selection_names():
    src = """
def record_research_run(path):
    frame = read_parquet(path)
    return zscore(frame)
"""
    assert is_selection_source(src) is False


def test_plain_read_service_is_not_mislabeled_as_selection():
    src = "def latest_prices():\n    return load_prices()\n"
    assert is_selection_source(src) is False


def test_discovery_is_explicitly_closed_world_classified():
    assert set(REQUIRED_ENTRYPOINTS) == set(REQUIRED)
    classified = set(REQUIRED) | set(DELEGATED) | set(EXEMPT)
    assert discover_selection_paths() <= classified


def test_island_chokepoint_rejects_holdout_data_before_search():
    dates = pd.bdate_range("2025-01-02", periods=3)
    frame = pd.DataFrame(1.0, index=dates, columns=["000001"])
    with pytest.raises(HoldoutBreach):
        run_island_search(
            frame, frame, frame, frame,
            vintage_id="holdout-probe",
            n_islands=1,
            generations=1,
            population=1,
        )


def test_empty_fixture_has_no_holdout_observation():
    assert_search_clean(pd.DatetimeIndex([]), label="empty unit fixture")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
