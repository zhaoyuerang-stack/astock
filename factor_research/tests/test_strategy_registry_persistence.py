"""Strategy registry persistence must be transactional, durable, and fail closed."""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

import strategy_registry as registry


def _register_family_batch(registry_path, prefix, count, start_event):
    import strategy_registry as child_registry

    child_registry.REGISTRY = Path(registry_path)
    if not start_event.wait(timeout=10):
        raise RuntimeError("timed out waiting to start concurrent family registrations")
    for index in range(count):
        family_id = f"{prefix}-{index}"
        child_registry.register_family(family_id, f"Family {family_id}")


def _register_version_batch(registry_path, prefix, count, start_event):
    import strategy_registry as child_registry

    child_registry.REGISTRY = Path(registry_path)
    if not start_event.wait(timeout=10):
        raise RuntimeError("timed out waiting to start concurrent version registrations")
    for index in range(count):
        version = f"{prefix}-{index}"
        child_registry.register(
            "shared-family",
            version,
            f"Version {version}",
            config={},
            data_scope={},
            metrics={},
        )


def _run_concurrent_batches(target, registry_path, *, workers=4, count=8):
    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    processes = [
        context.Process(
            target=target,
            args=(str(registry_path), f"worker-{worker}", count, start_event),
        )
        for worker in range(workers)
    ]
    try:
        for process in processes:
            process.start()
        start_event.set()
        for process in processes:
            process.join(timeout=30)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
    assert [process.exitcode for process in processes] == [0] * workers


def test_concurrent_register_family_and_register_do_not_lose_updates(tmp_path, monkeypatch):
    registry_path = tmp_path / "strategy_versions.json"
    monkeypatch.setattr(registry, "REGISTRY", registry_path)

    _run_concurrent_batches(_register_family_batch, registry_path)
    data = registry._load()
    assert len(data["families"]) == 32
    assert len({family["id"] for family in data["families"]}) == 32

    registry.register_family("shared-family", "Shared Family")
    _run_concurrent_batches(_register_version_batch, registry_path)
    data = registry._load()
    shared = next(family for family in data["families"] if family["id"] == "shared-family")
    assert len(shared["versions"]) == 32
    assert len({version["version"] for version in shared["versions"]}) == 32


def test_replace_failure_preserves_previous_registry_and_cleans_temp(tmp_path, monkeypatch):
    registry_path = tmp_path / "strategy_versions.json"
    monkeypatch.setattr(registry, "REGISTRY", registry_path)
    registry.register_family("stable", "Stable")
    before = registry_path.read_bytes()

    def fail_replace(source, target):
        raise OSError("injected replace failure")

    monkeypatch.setattr(registry.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        registry.register_family("must-not-land", "Must Not Land")

    assert registry_path.read_bytes() == before
    assert not list(tmp_path.glob(f".{registry_path.name}.*.tmp"))


def test_invalid_existing_schema_blocks_mutation_without_overwrite(tmp_path, monkeypatch):
    registry_path = tmp_path / "strategy_versions.json"
    invalid = '{"families": {"not": "a list"}}'
    registry_path.write_text(invalid, encoding="utf-8")
    monkeypatch.setattr(registry, "REGISTRY", registry_path)

    with pytest.raises(registry.RegistryValidationError, match="families.*list"):
        registry.register_family("new", "New")

    assert registry_path.read_text(encoding="utf-8") == invalid


@pytest.mark.parametrize(
    "invalid_data",
    [
        {"families": "not-a-list"},
        {
            "families": [
                {"id": "duplicate", "versions": []},
                {"id": "duplicate", "versions": []},
            ],
        },
        {
            "families": [
                {
                    "id": "family",
                    "versions": [
                        {"version": "v1", "metrics": {"annual": float("nan")}},
                    ],
                },
            ],
        },
    ],
)
def test_prewrite_json_and_schema_validation_preserves_existing_file(
    tmp_path, monkeypatch, invalid_data
):
    registry_path = tmp_path / "strategy_versions.json"
    registry_path.write_text(json.dumps({"families": []}), encoding="utf-8")
    before = registry_path.read_bytes()
    monkeypatch.setattr(registry, "REGISTRY", registry_path)

    with pytest.raises(registry.RegistryValidationError):
        registry._save(invalid_data)

    assert registry_path.read_bytes() == before


def test_atomic_write_validates_temp_and_installed_file_and_fsyncs(
    tmp_path, monkeypatch
):
    registry_path = tmp_path / "strategy_versions.json"
    monkeypatch.setattr(registry, "REGISTRY", registry_path)
    read_paths = []
    fsync_calls = []
    real_read = registry._read_registry_file
    real_fsync = registry.os.fsync

    def tracking_read(path, **kwargs):
        read_paths.append(Path(path))
        return real_read(path, **kwargs)

    def tracking_fsync(file_descriptor):
        fsync_calls.append(file_descriptor)
        return real_fsync(file_descriptor)

    monkeypatch.setattr(registry, "_read_registry_file", tracking_read)
    monkeypatch.setattr(registry.os, "fsync", tracking_fsync)
    registry.register_family("family", "Family")

    assert registry_path in read_paths
    assert any(path.name.endswith(".tmp") for path in read_paths)
    assert len(fsync_calls) >= 2  # temporary file contents + parent directory entry
    assert registry._load()["families"][0]["id"] == "family"
    assert not list(tmp_path.glob(f".{registry_path.name}.*.tmp"))
