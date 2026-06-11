"""Stable fingerprints for candidate JSON ASTs."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint_ast(ast: dict) -> str:
    """Return a stable content hash for a candidate AST."""
    return hashlib.sha256(_canonical(ast).encode("utf-8")).hexdigest()[:16]
