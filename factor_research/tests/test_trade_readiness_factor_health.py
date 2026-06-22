"""trade_readiness 的 factor_health 必须读真实 decay 报告,不再硬编码 normal(机制修复)。

原 trade_readiness.py 把 factor_health 写死 "normal",交易就绪闸门永远当因子健康放行,
无论实际衰减。改为读 reports/decay_status.json,red→degraded 会拉低 allowed_to_trade。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import services.read.trade_readiness as TR


def _write_decay(tmp_path, status, strategies=()):
    rep = tmp_path / "reports"
    rep.mkdir()
    (rep / "decay_status.json").write_text(json.dumps({
        "status": status, "as_of_date": "2026-06-18", "generated_at": "2026-06-22T10:00:00+08:00",
        "strategies": list(strategies),
    }), encoding="utf-8")


def test_red_decay_maps_to_degraded(tmp_path, monkeypatch):
    monkeypatch.setattr(TR, "ROOT", tmp_path)
    _write_decay(tmp_path, "red", [{"strategy": "x.v1", "decayed": True}])
    health, meta = TR._factor_health_from_decay()
    assert health == "degraded"
    assert meta["decay_status"] == "red"
    assert meta["decayed_strategies"] == ["x.v1"]


def test_green_decay_maps_to_normal(tmp_path, monkeypatch):
    monkeypatch.setattr(TR, "ROOT", tmp_path)
    _write_decay(tmp_path, "green")
    assert TR._factor_health_from_decay()[0] == "normal"


def test_missing_report_is_unknown_not_normal(tmp_path, monkeypatch):
    # 报告缺失 → unknown(诚实),绝不退回假 normal
    monkeypatch.setattr(TR, "ROOT", tmp_path)
    health, meta = TR._factor_health_from_decay()
    assert health == "unknown"
    assert "缺失" in meta["note"] or "不可读" in meta["note"]


def test_degraded_health_blocks_auto_trade(tmp_path, monkeypatch):
    # factor_health=degraded 必须使 allowed_to_trade=False(衰减期不自动放行)
    monkeypatch.setattr(TR, "_factor_health_from_decay", lambda: ("degraded", {}))
    v = TR.get_trade_readiness()
    assert v.factor_health == "degraded"
    assert v.allowed_to_trade is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
