"""机构数据接入(2026-07-06,零抓取空白区首例):top_list(龙虎榜)注册项体检。

只测「注册表声明 + backfill 机制」的接线是否正确,不碰真实网络/token——
call() 与 _trade_dates() 全部 monkeypatch,LAKE 指向 tmp_path,不触真实数据湖。
"""
import json

import pandas as pd
import pytest

import scripts.data.update_tushare as ut


def _fixture_day(trade_date: str) -> pd.DataFrame:
    """还原实测发现的真实重复模式:同股同日可因多条不同上榜理由分别列示。"""
    return pd.DataFrame([
        {"trade_date": trade_date, "ts_code": "600397.SH", "name": "安源煤业",
         "close": 3.49, "pct_change": 10.09, "turnover_rate": 7.22, "amount": 248923651.0,
         "l_sell": 42598830.0, "l_buy": 127650066.25, "l_amount": 170248896.25,
         "net_amount": 85051236.25, "net_rate": 34.17, "amount_rate": 68.39,
         "float_values": 3454959988.18, "reason": "有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券"},
        {"trade_date": trade_date, "ts_code": "600397.SH", "name": "安源煤业",
         "close": 3.49, "pct_change": 10.09, "turnover_rate": 7.22, "amount": 295052863.0,
         "l_sell": 42666034.0, "l_buy": 137350226.59, "l_amount": 180016260.59,
         "net_amount": 94684192.59, "net_rate": 32.09, "amount_rate": 61.01,
         "float_values": 3454959988.18, "reason": "非ST、*ST和S证券连续三个交易日内收盘价格涨幅偏离值累计达到20%的证券"},
        {"trade_date": trade_date, "ts_code": "000759.SZ", "name": "中百集团",
         "close": 10.81, "pct_change": 9.97, "turnover_rate": 23.38, "amount": 1628982229.0,
         "l_sell": 256187123.3, "l_buy": 193235738.22, "l_amount": 449422861.52,
         "net_amount": -62951385.08, "net_rate": -3.86, "amount_rate": 27.59,
         "float_values": 7088182130.25, "reason": "日涨幅偏离值达到7%的前5只证券"},
    ])


@pytest.fixture
def isolated_lake(tmp_path, monkeypatch):
    lake = tmp_path / "data_lake"
    lake.mkdir()
    monkeypatch.setattr(ut, "LAKE", lake)
    monkeypatch.setattr(ut, "TU_MANIFEST", lake / "tushare_manifest.json")
    return lake


def test_top_list_dedup_keeps_distinct_reason_rows(isolated_lake, monkeypatch):
    """同 ts_code+trade_date 但 reason 不同的两行,dedup 必须都保留(不是重复行)。"""
    monkeypatch.setattr(ut, "_trade_dates", lambda start, end: ["20241227"])
    monkeypatch.setattr(ut, "call", lambda name, params, fields: _fixture_day(params["trade_date"]))

    ut.backfill("top_list", start="20241227", end="20241227")

    out = pd.read_parquet(isolated_lake / "institutional/top_list_all.parquet")
    assert len(out) == 3
    reasons = set(out.loc[out["ts_code"] == "600397.SH", "reason"])
    assert len(reasons) == 2, "同股同日不同上榜理由的两行被误删,dedup key 缺 reason"


def test_top_list_incremental_skips_existing_date(isolated_lake, monkeypatch):
    """已抓取的交易日不得重复调用 call()(增量应只补缺口)。"""
    calls = []

    def fake_call(name, params, fields):
        calls.append(params["trade_date"])
        return _fixture_day(params["trade_date"])

    monkeypatch.setattr(ut, "call", fake_call)
    monkeypatch.setattr(ut, "_trade_dates", lambda start, end: ["20241226", "20241227"])
    ut.backfill("top_list", start="20241226", end="20241227")
    assert calls == ["20241226", "20241227"]

    # 第二次跑同样窗口:两天都已存在,不应再触发任何 call()
    calls.clear()
    ut.backfill("top_list", start="20241226", end="20241227")
    assert calls == [], "增量未跳过已有交易日,重复消耗调用配额"


def test_top_list_manifest_stamped(isolated_lake, monkeypatch):
    """backfill 必须回写 manifest(R-ARCH-004:写湖核心区须可审计)。"""
    monkeypatch.setattr(ut, "_trade_dates", lambda start, end: ["20241227"])
    monkeypatch.setattr(ut, "call", lambda name, params, fields: _fixture_day(params["trade_date"]))

    ut.backfill("top_list", start="20241227", end="20241227")

    manifest = json.loads((isolated_lake / "tushare_manifest.json").read_text())
    assert "top_list" in manifest
    assert manifest["top_list"]["rows"] == 3
    assert manifest["top_list"]["last"] == "20241227"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
