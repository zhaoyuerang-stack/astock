from __future__ import annotations

import json

from lake.artifact_writer import append_jsonl, atomic_write_json, atomic_write_text


def test_atomic_writer_replaces_complete_payload_and_preserves_requested_mode(tmp_path):
    target = tmp_path / "data_lake" / "agent" / "config.json"
    atomic_write_text(target, "old", mode=0o600)
    atomic_write_json(target, {"state": "new"}, mode=0o600)

    assert json.loads(target.read_text(encoding="utf-8")) == {"state": "new"}
    assert target.stat().st_mode & 0o777 == 0o600
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))


def test_jsonl_writer_appends_complete_rows(tmp_path):
    target = tmp_path / "data_lake" / "governance" / "events.jsonl"
    append_jsonl(target, {"id": 1})
    append_jsonl(target, [{"id": 2}, {"id": 3}])

    assert [json.loads(line) for line in target.read_text().splitlines()] == [
        {"id": 1}, {"id": 2}, {"id": 3},
    ]
