"""ALFRED adapter tests use injected responses and never call the network."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_alfred_provider_requires_an_explicit_api_key():
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.sources.alfred_macro import AlfredMacroProvider

    provider = AlfredMacroProvider(source=get_source_spec("alfred_macro_v1"), environ={})
    status = provider.probe(get_dataset_spec("macro_daily"))

    assert status["ok"] is False
    assert status["status"] == "missing_credentials"
    assert "FRED_API_KEY" in status["error"]


def test_alfred_provider_maps_metadata_and_vintage_to_raw_contract():
    from lake.global_catalog import get_dataset_spec, get_source_spec
    from lake.sources.alfred_macro import AlfredMacroProvider

    source = replace(
        get_source_spec("alfred_macro_v1"),
        admission_status="approved",
        license_status="approved",
        license_checked_at="2026-07-10",
    )
    calls = []

    def request_json(path, params):
        calls.append((path, params))
        if path.endswith("/series"):
            return {"seriess": [{"units": "Percent", "frequency_short": "D"}]}
        if path.endswith("/series/observations"):
            return {
                "observations": [{
                    "date": "2026-07-01",
                    "value": "4.25",
                    "realtime_start": "2026-07-02",
                    "realtime_end": "9999-12-31",
                }]
            }
        raise AssertionError(path)

    provider = AlfredMacroProvider(
        source=source,
        environ={"FRED_API_KEY": "test-key"},
        request_json=request_json,
    )
    status = provider.probe(get_dataset_spec("macro_daily"))
    raw = provider.fetch(get_dataset_spec("macro_daily"), start="2026-07-01", end="2026-07-31")

    assert status["ok"] is True
    assert raw.to_dict("records") == [{
        "series_id": "DFF",
        "observation_date": "2026-07-01",
        "value": "4.25",
        "unit": "Percent",
        "frequency": "daily",
        "vintage_start": "2026-07-02",
        "vintage_end": "9999-12-31",
        "available_at": "2026-07-03T04:59:59+00:00",
    }]
    assert calls[0][0].endswith("/series")
    assert calls[1][0].endswith("/series/observations")
    assert all(call[1]["api_key"] == "test-key" for call in calls)
    assert calls[1][1]["observation_start"] == "2026-07-01"
    assert calls[1][1]["realtime_start"] == "1776-07-04"
