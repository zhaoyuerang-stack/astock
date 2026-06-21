import json

import numpy as np
import pandas as pd
import pytest

from governance.holdout import (
    HoldoutAlreadyConsumed,
    HoldoutIdentityMismatch,
    validate_on_holdout,
)


def _returns():
    idx = pd.date_range("2024-01-01", "2026-01-30", freq="B")
    return pd.Series(np.random.default_rng(7).normal(0.001, 0.01, len(idx)), index=idx)


def _validate(path, **kwargs):
    return validate_on_holdout(
        "candidate-a",
        _returns(),
        spec_hash="spec-a",
        data_fingerprint="data-a",
        path=path,
        **kwargs,
    )


def test_same_identity_retry_is_idempotent(tmp_path):
    path = tmp_path / "holdout.jsonl"

    first = _validate(path)
    second = _validate(path)

    assert first["peek_count"] == 1
    assert second["peek_count"] == 1
    assert second["idempotent_retry"] is True
    assert len(path.read_text().splitlines()) == 1


def test_active_second_evaluation_is_rejected(tmp_path):
    path = tmp_path / "holdout.jsonl"
    _validate(path)

    with pytest.raises(HoldoutAlreadyConsumed):
        _validate(path, idempotent_retry=False)


def test_changed_spec_requires_new_candidate_identity(tmp_path):
    path = tmp_path / "holdout.jsonl"
    _validate(path)

    with pytest.raises(HoldoutIdentityMismatch):
        validate_on_holdout(
            "candidate-a",
            _returns(),
            spec_hash="spec-b",
            data_fingerprint="data-a",
            path=path,
        )


def test_record_contains_full_identity_and_return_hash(tmp_path):
    path = tmp_path / "holdout.jsonl"
    _validate(path)

    record = json.loads(path.read_text().strip())
    assert record["candidate_id"] == "candidate-a"
    assert record["spec_hash"] == "spec-a"
    assert record["data_fingerprint"] == "data-a"
    assert record["holdout_boundary"] == "2025-01-01"
    assert len(record["return_hash"]) == 64
    assert record["consumed_at"]
