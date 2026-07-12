"""paper 文案必须与 paper_engine.FILL_PRICE_MODE 一致(审计:开盘/收盘混用)。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from portfolio import paper_engine as pe
from scripts.ops import paper_trade as pt


def test_default_fill_mode_is_close():
    assert pe.resolve_fill_mode() == "close"
    assert pe.fill_mode_label() == "收盘价"
    assert "收盘价" in pe.fill_mode_zh()
    assert "开盘价" not in pe.fill_mode_zh()


def test_fill_mode_labels_for_all_modes():
    assert pe.fill_mode_label("open") == "开盘价"
    assert pe.fill_mode_label("close") == "收盘价"
    assert pe.fill_mode_label("ohlc_mid") == "OHLC中价"
    with pytest.raises(ValueError):
        pe.resolve_fill_mode("garbage")


def test_render_card_uses_fill_mode_not_hardcoded_open(monkeypatch):
    """默认 close 时卡片不得写「T+1 开盘成交」/表格「开盘价」。"""
    monkeypatch.setattr(pe, "FILL_PRICE_MODE", "close")
    # paper_trade imports FILL_PRICE_MODE at module level — rebind helpers
    monkeypatch.setattr(pt, "FILL_PRICE_MODE", "close")
    monkeypatch.setattr(pt, "fill_mode_label", lambda mode=None: pe.fill_mode_label("close"))
    monkeypatch.setattr(pt, "fill_mode_zh", lambda mode=None: pe.fill_mode_zh("close"))
    monkeypatch.setattr(pt, "fill_mode_disclaimer", lambda mode=None: pe.fill_mode_disclaimer("close"))

    acc = {
        "init_capital": 1_000_000.0,
        "cash": 1_000_000.0,
        "positions": {},
        "inception": "2026-01-01",
        "pending": {"target": ["600519"], "bond": {}},
    }
    signal = {
        "in_market": True,
        "top_n": 1,
        "holdings": ["600519"],
        "small_index_vs_ma16": 0.01,
        "strategy_version": "v1.0",
    }
    trades = [("2026-07-11", "600519", "茅台", "BUY", 100, 1800.0, 180000.0)]
    card = pt.render_card(
        "2026-07-11", signal, None, acc,
        nav=1_000_000.0, pos_value=0.0, detail=[],
        trades=trades, blocked=[], names={"600519": "茅台"},
        exec_from="2026-07-10",
    )
    assert "收盘价" in card
    assert "mode=close" in card or "FILL_PRICE_MODE=`close`" in card or "mode=`close`" in card
    # 禁止旧的硬编码开盘成交叙事
    assert "T+1 开盘价" not in card
    assert "T+1 开盘成交" not in card
    assert "真实盘 T+1 开盘成交" not in card
    # 表格列名应是收盘价而非开盘价
    assert "| 收盘价 |" in card or "收盘价" in card
    assert "开盘价" not in card or "涨跌停" in card  # 涨跌停说明可提开盘价


def test_render_card_open_mode_says_open(monkeypatch):
    monkeypatch.setattr(pt, "FILL_PRICE_MODE", "open")
    monkeypatch.setattr(pt, "fill_mode_label", lambda mode=None: pe.fill_mode_label("open"))
    monkeypatch.setattr(pt, "fill_mode_zh", lambda mode=None: pe.fill_mode_zh("open"))
    monkeypatch.setattr(pt, "fill_mode_disclaimer", lambda mode=None: pe.fill_mode_disclaimer("open"))

    acc = {
        "init_capital": 1_000_000.0, "cash": 1_000_000.0, "positions": {},
        "inception": "2026-01-01", "pending": {},
    }
    signal = {"in_market": False, "top_n": 25, "holdings": [],
              "small_index_vs_ma16": -0.01, "strategy_version": "v1.0"}
    card = pt.render_card(
        "2026-07-11", signal, None, acc,
        nav=1e6, pos_value=0.0, detail=[],
        trades=[], blocked=[], names={}, exec_from=None,
    )
    assert "开盘价" in card
    assert "mode=open" in card or "mode=`open`" in card


def test_services_read_disclaimer_tracks_fill_mode():
    from services.read import paper as rp
    # module-level DISCLAIMER evaluated at import — check helpers still used
    assert pe.fill_mode_label() in rp.DISCLAIMER or pe.fill_mode_zh() in rp.DISCLAIMER
    assert pe.FILL_PRICE_MODE in rp.DISCLAIMER or pe.fill_mode_zh() in rp.DISCLAIMER


def test_adversarial_paper_trade_source_no_stale_t1_open_claim():
    """对抗: paper_trade 源码不得再声称固定 T+1 开盘成交(默认已是 close)。"""
    src = (ROOT / "scripts/ops/paper_trade.py").read_text(encoding="utf-8")
    # 允许注释解释涨跌停用开盘,禁止把成交默认写成开盘
    assert "真实盘 T+1 开盘成交" not in src
    assert "T+1 开盘价**成交" not in src
    assert "fill_mode_label" in src
    assert "FILL_PRICE_MODE" in src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
