"""Canonical writer for strategy version return series."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data_lake" / "version_returns"


def _safe_part(value: str) -> str:
    return str(value).replace("/", "_").replace(" ", "_")


def version_returns_path(family: str, version: str, *, root: Path | None = None) -> Path:
    base = root or STORE
    return base / f"{_safe_part(family)}__{_safe_part(version)}.csv"


def write_version_returns(
    returns: pd.Series,
    *,
    family: str,
    version: str,
    root: Path | None = None,
) -> Path:
    if returns is None or len(returns) == 0:
        raise ValueError("returns must be a non-empty Series")
    path = version_returns_path(family, version, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            fd = -1
            returns.rename("ret").to_csv(handle, header=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        tmp.unlink(missing_ok=True)
    return path
