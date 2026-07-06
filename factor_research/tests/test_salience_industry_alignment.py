"""Salience research industry alignment must be point-in-time."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_salience_industry_panel_uses_avail_date(monkeypatch):
    from scripts.research import salience_industry

    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    close = pd.DataFrame(index=dates, columns=["000001", "000002"], dtype=float)

    def fake_load_fundamental_panel(trade_dates, codes=None, fields=None):
        assert list(trade_dates) == list(dates)
        assert codes == ["000001", "000002"]
        assert fields == ["industry"]
        return {
            "industry": pd.DataFrame(
                {
                    "000001": [pd.NA, "OldBank", "NewTech"],
                    "000002": ["Broker", "Broker", "Broker"],
                },
                index=dates,
            )
        }

    monkeypatch.setattr(
        salience_industry,
        "load_fundamental_panel",
        fake_load_fundamental_panel,
    )

    out = salience_industry.build_avail_date_industry_panel(close)

    assert out.index.equals(close.index)
    assert list(out.columns) == ["000001", "000002"]
    assert out.loc["2020-01-01", "000001"] == "Unknown"
    assert out.loc["2020-01-02", "000001"] == "OldBank"
    assert out.loc["2020-01-03", "000001"] == "NewTech"
    assert out.loc["2020-01-01", "000002"] == "Broker"
