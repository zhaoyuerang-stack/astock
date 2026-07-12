"""分层抽样质量门(审计:原 5 只大票过浅)。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from lake.sample_quality import (
    DEFAULT_ANCHORS,
    classify_board,
    list_daily_codes,
    run_sample_quality_check,
    select_sample_codes,
)


def test_classify_board_strata():
    assert classify_board("600519") == "main"
    assert classify_board("000001") == "main"
    assert classify_board("300750") == "chinext"
    assert classify_board("301001") == "chinext"
    assert classify_board("688981") == "star"
    assert classify_board("830799") == "bse" or classify_board("830799") in ("bse", "main")


def test_select_sample_includes_anchors_and_strata():
    # Synthetic universe
    codes = (
        [f"{600000 + i:06d}" for i in range(50)]
        + [f"{300000 + i:06d}" for i in range(40)]
        + [f"{688000 + i:06d}" for i in range(30)]
        + ["600519", "000001", "300750"]
    )
    sample = select_sample_codes(codes, seed="2026-07-10")
    assert "600519" in sample
    assert "000001" in sample
    assert "300750" in sample
    strata = {classify_board(c) for c in sample}
    assert "main" in strata
    assert "chinext" in strata
    assert "star" in strata
    # Much deeper than 5 fixed names
    assert len(sample) > 20


def test_select_sample_deterministic_for_same_seed():
    codes = [f"{600000 + i:06d}" for i in range(100)] + [f"{300000 + i:06d}" for i in range(50)]
    a = select_sample_codes(codes, seed="2026-07-10")
    b = select_sample_codes(codes, seed="2026-07-10")
    c = select_sample_codes(codes, seed="2026-07-11")
    assert a == b
    assert a != c or len(codes) < 10  # different seed → different draw (if enough codes)


def test_run_sample_quality_on_tmp_lake(tmp_path: Path):
    """对抗: 只有 5 锚点时也能跑;注入 OHLC 坏数据必须进 bad。"""
    daily = tmp_path / "data_lake" / "price" / "daily"
    daily.mkdir(parents=True)
    cal_dir = tmp_path / "data_lake" / "meta"
    cal_dir.mkdir(parents=True)
    dates = pd.bdate_range("2024-01-02", periods=30)
    cal = pd.DataFrame({"date": dates})
    cal.to_parquet(cal_dir / "trade_calendar.parquet")

    def _write(code: str, *, bad_ohlc: bool = False):
        df = pd.DataFrame({
            "date": dates,
            "open": 10.0,
            "high": 11.0 if not bad_ohlc else 9.0,  # high < open → OHLC error
            "low": 9.0,
            "close": 10.5,
            "volume": 1e6,
            "amount": 1e7,
        })
        df.to_parquet(daily / f"{code}.parquet")

    for code in ["600519", "000001", "300750", "600036", "601398", "688001", "300001"]:
        _write(code, bad_ohlc=(code == "688001"))

    report = run_sample_quality_check(
        tmp_path,
        seed="fixed",
        per_stratum={"main": 2, "chinext": 1, "star": 1, "bse": 0},
    )
    assert report["n_checked"] >= 5
    assert report["mode"] == "stratified_sample"
    assert any(row["code"] == "688001" for row in report["bad"])
    assert report["ok"] is False
    assert "star" in report["strata_checked"] or "main" in report["strata_checked"]


def test_run_sample_quality_clean_tmp(tmp_path: Path):
    daily = tmp_path / "data_lake" / "price" / "daily"
    daily.mkdir(parents=True)
    cal_dir = tmp_path / "data_lake" / "meta"
    cal_dir.mkdir(parents=True)
    dates = pd.bdate_range("2024-01-02", periods=40)
    pd.DataFrame({"date": dates}).to_parquet(cal_dir / "trade_calendar.parquet")
    for code in list(DEFAULT_ANCHORS)[:5] + ["688001", "300001", "002001"]:
        pd.DataFrame({
            "date": dates,
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.5,
            "volume": 1e6,
            "amount": 1e7,
        }).to_parquet(daily / f"{code}.parquet")

    report = run_sample_quality_check(tmp_path, seed="clean")
    assert report["ok"] is True
    assert report["n_bad"] == 0
    assert report["n_checked"] > 5


def test_adversarial_old_five_name_only_is_not_enough_universe():
    """对抗: 仅 5 只大票不得被当作「全市场抽样」——选择器在更大宇宙上必须扩样。"""
    tiny = list(DEFAULT_ANCHORS[:5])
    big = tiny + [f"{600100 + i:06d}" for i in range(80)] + [f"{300100 + i:06d}" for i in range(40)]
    s_tiny = select_sample_codes(tiny, seed="d")
    s_big = select_sample_codes(big, seed="d")
    assert len(s_tiny) <= 5
    assert len(s_big) > 15


@pytest.mark.requires_data_lake
def test_live_stratified_sample_covers_boards():
    """真湖: 抽样须跨板且远超 5 只。"""
    available = list_daily_codes(ROOT / "data_lake" / "price" / "daily")
    if len(available) < 100:
        pytest.skip("daily lake too small")
    sample = select_sample_codes(available, seed="2026-07-10")
    assert len(sample) > 30
    boards = {classify_board(c) for c in sample}
    assert "main" in boards and "chinext" in boards and "star" in boards

    # Smoke: full check finishes and reports structure
    report = run_sample_quality_check(ROOT, seed="2026-07-10")
    assert report["n_checked"] > 30
    assert "strata_checked" in report
    assert report["mode"] == "stratified_sample"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
