"""Canonical durable writers for mutable artifacts under ``data_lake``.

Callers own schema validation; this module owns crash-safe replacement,
append serialization, fsync, and restrictive modes for secret-bearing files.
Keeping the actual filesystem writes here lets the lake-writer guard enforce a
closed write boundary without granting broad exemptions to tests or scripts.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
import tempfile
import threading
from pathlib import Path
from typing import Any, Iterable


_PROCESS_APPEND_LOCK = threading.RLock()


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_bytes(path: str | Path, payload: bytes, *, mode: int | None = None) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    effective_mode = mode
    if effective_mode is None:
        effective_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
    descriptor, temp_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary = Path(temp_name)
    try:
        os.fchmod(descriptor, effective_mode)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(bytes(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        _fsync_parent(target)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    return target


def atomic_write_text(
    path: str | Path,
    payload: str,
    *,
    encoding: str = "utf-8",
    mode: int | None = None,
) -> Path:
    return atomic_write_bytes(path, str(payload).encode(encoding), mode=mode)


def atomic_write_json(
    path: str | Path,
    payload: Any,
    *,
    mode: int | None = None,
    default=None,
) -> Path:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
        default=default,
    ) + "\n"
    return atomic_write_text(path, text, mode=mode)


def append_jsonl(path: str | Path, records: dict | Iterable[dict]) -> Path:
    target = Path(path)
    rows = [records] if isinstance(records, dict) else list(records)
    encoded = "".join(
        json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + "\n"
        for row in rows
    )
    if not encoded:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(f".{target.name}.lock")
    with _PROCESS_APPEND_LOCK:
        with lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                with target.open("a", encoding="utf-8") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    return target
