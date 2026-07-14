import pandas as pd
import pytest

from scripts.research.validate_industry_cap_regime import _event_starts, load_benchmark


def test_event_starts_enforces_cooldown():
    index = pd.date_range("2024-01-01", periods=30, freq="D")
    mask = pd.Series(False, index=index)
    mask.iloc[[1, 2, 10, 11, 25]] = True

    starts = _event_starts(mask, cooldown=20)

    assert list(starts[starts].index) == [index[1], index[25]]


def test_benchmark_compounds_returns_without_level_join_jump(tmp_path):
    rows = [
        {"ts_code": "000300.SH", "trade_date": "20240101", "close": 100.0},
        {"ts_code": "000300.SH", "trade_date": "20240102", "close": 110.0},
        {"ts_code": "000300.SH", "trade_date": "20240103", "close": 121.0},
        {"ts_code": "000905.SH", "trade_date": "20240102", "close": 1000.0},
        {"ts_code": "000905.SH", "trade_date": "20240103", "close": 1100.0},
    ]
    path = tmp_path / "indices.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)

    benchmark = load_benchmark(path)

    assert benchmark.loc["2024-01-02"] == pytest.approx(1.1)
    assert benchmark.loc["2024-01-03"] == pytest.approx(1.21)
