"""Factory line L0-L3 holdout chokepoint.

Callers (pipeline / CLI / research_stages) must still truncate panels, but
direct ``run_l0(full_close, ...)`` must not be able to score the vault.
"""
from __future__ import annotations

from typing import Any


def assert_factory_panels_clean(
    close,
    volume=None,
    amount=None,
    forward_ret=None,
    *,
    label: str,
) -> None:
    """Raise HoldoutBreach if any panel index reaches the holdout vault.

    Empty / None panels are ignored (unit fixtures); real selection fails later
    on empty data. Must run **before** factor compute so peek never happens.
    """
    from governance.holdout import assert_search_clean

    assert_search_clean(_index_or_none(close), label=f"{label} close")
    if volume is not None:
        assert_search_clean(_index_or_none(volume), label=f"{label} volume")
    if amount is not None:
        assert_search_clean(_index_or_none(amount), label=f"{label} amount")
    if forward_ret is not None:
        assert_search_clean(_index_or_none(forward_ret), label=f"{label} forward_ret")


def _index_or_none(obj: Any):
    if obj is None:
        return None
    if hasattr(obj, "index"):
        return obj.index
    return obj
