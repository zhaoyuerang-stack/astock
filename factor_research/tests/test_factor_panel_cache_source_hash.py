"""factor_store/panels 磁盘缓存 key 必须含因子源码摘要。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factors.autoresearch_dsl import _factor_source_hash, _get_cache_path


def test_source_hash_stable_and_nonempty():
    h1 = _factor_source_hash("momentum")
    h2 = _factor_source_hash("momentum")
    assert h1 == h2
    assert h1 not in {"", "unknown"}
    assert len(h1) >= 8


def test_cache_path_includes_src_suffix():
    path = _get_cache_path("momentum", {"window": 20}, data_signature=None)
    assert "_src" in path.name
    assert path.parent.name == "panels"
    assert "factor_store" in path.parts


def test_different_factors_different_source_hash():
    assert _factor_source_hash("momentum") != _factor_source_hash("volatility")


if __name__ == "__main__":
    test_source_hash_stable_and_nonempty()
    test_cache_path_includes_src_suffix()
    test_different_factors_different_source_hash()
    print("ok")
