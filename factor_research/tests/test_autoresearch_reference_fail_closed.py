from __future__ import annotations

import pandas as pd
import pytest

from services.actions.autoresearch_search import _style_panels, active_book_panels


def _frames():
    index = pd.bdate_range("2024-01-01", periods=5)
    close = pd.DataFrame(10.0, index=index, columns=["000001"])
    volume = pd.DataFrame(100.0, index=index, columns=close.columns)
    amount = close * volume
    return close, volume, amount


def test_missing_active_book_leg_blocks_correlation_selection(monkeypatch):
    close, volume, amount = _frames()

    def broken(*args, **kwargs):
        raise ValueError("fixture failure")

    monkeypatch.setattr("factors.small_cap.small_cap_factor", broken)
    with pytest.raises(RuntimeError, match="active-book reference"):
        active_book_panels(close, volume, amount)


def test_missing_style_data_blocks_orthogonality_selection(monkeypatch):
    close, _, _ = _frames()

    def broken(*args, **kwargs):
        raise FileNotFoundError("fixture failure")

    monkeypatch.setattr("lake.load_lake.load_tushare_panel", broken)
    with pytest.raises(RuntimeError, match="style reference"):
        _style_panels(close)
