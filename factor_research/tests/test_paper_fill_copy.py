"""paper 文案必须与 paper_engine.FILL_PRICE_MODE 一致(审计:开盘/收盘混用)。

对抗矩阵:
  · 默认 mode=close → 文案/卡片/API disclaimer 不得写「T+1 开盘成交」
  · mode=open 时文案必须切到开盘价
  · 执行路径 buyable/sellable 走 get_fill_price(mode),不是死写 get_open
  · 源码扫描:展示层禁固定「T+1 开盘成交」字面
  · TradePlanView 暴露 fill_mode 与引擎一致
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from portfolio import paper_engine as pe
from scripts.ops import paper_trade as pt


def _bind_mode(monkeypatch, mode: str):
    monkeypatch.setattr(pe, "FILL_PRICE_MODE", mode)
    monkeypatch.setattr(pt, "FILL_PRICE_MODE", mode)
    monkeypatch.setattr(pt, "fill_mode_label", lambda m=None: pe.fill_mode_label(mode))
    monkeypatch.setattr(pt, "fill_mode_zh", lambda m=None: pe.fill_mode_zh(mode))
    monkeypatch.setattr(pt, "fill_mode_disclaimer", lambda m=None: pe.fill_mode_disclaimer(mode))


def test_default_fill_mode_is_close():
    assert pe.resolve_fill_mode() == "close"
    assert pe.fill_mode_label() == "收盘价"
    assert "收盘价" in pe.fill_mode_zh()
    assert "开盘价" not in pe.fill_mode_zh()


def test_fill_mode_labels_for_all_modes():
    assert pe.fill_mode_label("open") == "开盘价"
    assert pe.fill_mode_label("close") == "收盘价"
    assert pe.fill_mode_label("ohlc_mid") == "OHLC中价"
    assert pe.fill_mode_label("vwap_4") == "VWAP(OHLC/4)"
    with pytest.raises(ValueError):
        pe.resolve_fill_mode("garbage")


def test_disclaimer_separates_fill_from_limit_constraint():
    """对抗: disclaimer 必须同时说清「成交价模式」与「涨跌停仍看开盘」。"""
    d = pe.fill_mode_disclaimer("close")
    assert "收盘价" in d
    assert "开盘价" in d  # 涨跌停约束
    assert "pending" in d or "信号" in d


def test_render_card_uses_fill_mode_not_hardcoded_open(monkeypatch):
    """默认 close 时卡片不得写「T+1 开盘成交」/表格「开盘价」作成交列。"""
    _bind_mode(monkeypatch, "close")

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
    assert "T+1 开盘价" not in card
    assert "T+1 开盘成交" not in card
    assert "真实盘 T+1 开盘成交" not in card
    assert "次日开盘执行" not in card
    assert "次日开盘买入" not in card
    # 成交表格列必须是收盘价
    assert "| 收盘价 |" in card
    # 涨跌停说明可提开盘价,但不得把成交写成开盘
    assert "涨跌停" in card


def test_render_card_open_mode_says_open(monkeypatch):
    _bind_mode(monkeypatch, "open")

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
    assert "收盘价成交" not in card  # open 模式不得写 close 叙事


def test_adversarial_flip_mode_flips_card_header(monkeypatch):
    """对抗: 同一 render 路径, mode 切换必须改标题成交措辞。"""
    acc = {
        "init_capital": 1e6, "cash": 1e6, "positions": {},
        "inception": "2026-01-01", "pending": {},
    }
    signal = {"in_market": False, "top_n": 25, "holdings": [],
              "small_index_vs_ma16": 0.0, "strategy_version": "v1.0"}

    _bind_mode(monkeypatch, "close")
    c_close = pt.render_card(
        "2026-07-11", signal, None, acc,
        nav=1e6, pos_value=0.0, detail=[], trades=[], blocked=[], names={}, exec_from=None,
    )
    _bind_mode(monkeypatch, "open")
    c_open = pt.render_card(
        "2026-07-11", signal, None, acc,
        nav=1e6, pos_value=0.0, detail=[], trades=[], blocked=[], names={}, exec_from=None,
    )
    assert "T+1 收盘价成交" in c_close
    assert "T+1 开盘价成交" in c_open
    assert c_close != c_open


def test_buyable_uses_get_fill_price_not_raw_open(monkeypatch):
    """对抗: 可买价必须走 get_fill_price(mode),close 模式不得返回 open。"""
    calls = []

    def fake_open(code, date):
        return 10.0  # 开盘

    def fake_prev(code, date):
        return 10.0

    def fake_fill(code, date, mode=None):
        calls.append(mode or pe.FILL_PRICE_MODE)
        return 11.5  # 收盘

    monkeypatch.setattr(pe, "FILL_PRICE_MODE", "close")
    monkeypatch.setattr(pe, "get_open", fake_open)
    monkeypatch.setattr(pe, "get_prev_close", fake_prev)
    monkeypatch.setattr(pe, "get_fill_price", fake_fill)
    monkeypatch.setattr(pe, "limit_pct", lambda code, name: 0.1)

    px = pe.buyable_open("600519", "2026-07-11", "茅台")
    assert px == 11.5  # 必须是 fill 价,不是 open 10
    assert calls == ["close"]


def test_sellable_uses_get_fill_price(monkeypatch):
    monkeypatch.setattr(pe, "FILL_PRICE_MODE", "close")
    monkeypatch.setattr(pe, "get_open", lambda *a, **k: 10.0)
    monkeypatch.setattr(pe, "get_prev_close", lambda *a, **k: 10.0)
    monkeypatch.setattr(pe, "get_fill_price", lambda *a, **k: 9.5)
    monkeypatch.setattr(pe, "limit_pct", lambda *a, **k: 0.1)
    assert pe.sellable_open("000001", "2026-07-11", "平安") == 9.5


def test_services_read_disclaimer_tracks_fill_mode():
    from services.read import paper as rp
    assert pe.fill_mode_label() in rp.DISCLAIMER or pe.fill_mode_zh() in rp.DISCLAIMER
    assert pe.FILL_PRICE_MODE in rp.DISCLAIMER or pe.fill_mode_zh() in rp.DISCLAIMER


def test_trade_plan_view_exposes_fill_mode(monkeypatch):
    """对抗: API TradePlanView 必须带 fill_mode,且与引擎默认一致。"""
    from contracts.views import TradePlanView
    from services.read import paper as rp

    # trade_plan 依赖账户/信号文件;只断言 schema 默认 + 模块常量接线
    v = TradePlanView()
    assert v.fill_mode == "close"
    assert v.fill_mode_label == "收盘价"
    assert rp.FILL_PRICE_MODE == pe.FILL_PRICE_MODE


def test_adversarial_paper_trade_source_no_stale_t1_open_claim():
    """对抗: paper_trade 源码不得再声称固定 T+1 开盘成交(默认已是 close)。"""
    src = (ROOT / "scripts/ops/paper_trade.py").read_text(encoding="utf-8")
    assert "真实盘 T+1 开盘成交" not in src
    assert "T+1 开盘价**成交" not in src
    assert "次日开盘执行" not in src
    assert "次日开盘买入" not in src
    assert "实际按开盘价" not in src
    assert "fill_mode_label" in src
    assert "FILL_PRICE_MODE" in src


def test_adversarial_paper_engine_execute_comments_not_claim_open_fill():
    """对抗: execute_to_target 注释不得再写「用 date 开盘价」成交。"""
    src = (ROOT / "portfolio/paper_engine.py").read_text(encoding="utf-8")
    assert "用 date 开盘价" not in src
    assert "FILL_PRICE_MODE" in src
    assert "fill_mode_label" in src


def test_adversarial_services_paper_bond_notes_use_helper():
    src = (ROOT / "services/read/paper.py").read_text(encoding="utf-8")
    assert "次日开盘卖出全部国债ETF" not in src
    assert "fill_mode_label()" in src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
