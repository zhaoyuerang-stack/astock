"""Native Alpha Vantage commodity spot adapter."""
from __future__ import annotations

import json
import os
from datetime import datetime, time, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from lake.global_catalog import DatasetSpec, SourceSpec
from lake.sources.openbb_global import ProviderUnavailable


ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

_SERIES_SPECS = {
    "CL=F": {"function": "WTI"},
    "BZ=F": {"function": "BRENT"},
    "NG=F": {"function": "NATURAL_GAS"},
    "GC=F": {"function": "GOLD_SILVER_HISTORY", "symbol": "GOLD"},
    "SI=F": {"function": "GOLD_SILVER_HISTORY", "symbol": "SILVER"},
}


class AlphaVantageCommodityProvider:
    provider = "alphavantage"

    def __init__(
        self,
        *,
        source: SourceSpec,
        environ: Mapping[str, str] | None = None,
        request_json: Callable[[dict[str, str]], dict[str, Any]] | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.source = source
        self._environ = environ if environ is not None else os.environ
        self._request_json = request_json
        self.timeout_seconds = timeout_seconds

    @property
    def _api_key(self) -> str:
        return str(self._environ.get(self.source.api_key_env, "")) if self.source.api_key_env else ""

    def probe(self, spec: DatasetSpec) -> dict[str, Any]:
        if spec.dataset_id not in self.source.datasets:
            return {
                "ok": False,
                "provider": self.provider,
                "source_id": self.source.source_id,
                "dataset_id": spec.dataset_id,
                "status": "source_not_admitted",
                "error": f"{self.source.source_id} is not admitted for {spec.dataset_id}",
            }
        if not self._api_key:
            return {
                "ok": False,
                "provider": self.provider,
                "source_id": self.source.source_id,
                "dataset_id": spec.dataset_id,
                "status": "missing_credentials",
                "error": f"missing API key env: {self.source.api_key_env}",
            }
        return {
            "ok": True,
            "provider": self.provider,
            "source_id": self.source.source_id,
            "dataset_id": spec.dataset_id,
            "status": "available",
        }

    def _request(self, params: dict[str, str]) -> dict[str, Any]:
        if self._request_json is not None:
            return self._request_json(params)
        query = dict(params)
        query["apikey"] = self._api_key
        url = f"{ALPHA_VANTAGE_BASE_URL}?{urlencode(query)}"
        with urlopen(url, timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed official endpoint.
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _session_close_at(day: str) -> str:
        stamp = datetime.combine(datetime.fromisoformat(day).date(), time(23, 59, 59), tzinfo=timezone.utc)
        return stamp.isoformat(timespec="seconds")

    @staticmethod
    def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if "Error Message" in payload:
            raise ProviderUnavailable(str(payload["Error Message"]))
        if "Note" in payload:
            raise ProviderUnavailable(str(payload["Note"]))
        data = payload.get("data")
        if not isinstance(data, list):
            raise ProviderUnavailable("Alpha Vantage commodity payload missing data array")
        return [dict(item) for item in data]

    def fetch(self, spec: DatasetSpec, *, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        status = self.probe(spec)
        if not status.get("ok"):
            raise ProviderUnavailable(status.get("error") or status.get("status") or "provider unavailable")
        if spec.dataset_id != "commodity_daily":
            raise ProviderUnavailable(f"Alpha Vantage commodity adapter is not configured for {spec.dataset_id}")
        if not start:
            raise ProviderUnavailable("initial Alpha Vantage commodity history fetch requires an explicit start date")

        start_day = pd.Timestamp(start).normalize()
        end_day = pd.Timestamp(end).normalize() if end else None
        rows: list[dict[str, Any]] = []
        for canonical_symbol in self.source.allowlist_for(spec.dataset_id):
            query = dict(_SERIES_SPECS.get(canonical_symbol) or {})
            if not query:
                raise ProviderUnavailable(f"no Alpha Vantage query mapping for {canonical_symbol}")
            query["datatype"] = "json"
            query["interval"] = "daily"
            payload = self._request(query)
            for item in self._extract_rows(payload):
                session_date = pd.Timestamp(str(item.get("date"))).normalize()
                if session_date < start_day:
                    continue
                if end_day is not None and session_date > end_day:
                    continue
                close = pd.to_numeric(item.get("value"), errors="coerce")
                rows.append({
                    "symbol": canonical_symbol,
                    "exchange": "ALPHAVANTAGE_SPOT",
                    "session_date": session_date,
                    "session_close_at": self._session_close_at(session_date.date().isoformat()),
                    "available_at": self._session_close_at(session_date.date().isoformat()),
                    "open": pd.NA,
                    "high": pd.NA,
                    "low": pd.NA,
                    "close": close,
                    "volume": 0.0,
                    "is_adjusted": False,
                    "adjustment_version": "alphavantage_spot_v1",
                    "currency": self.source.currency,
                })
        return pd.DataFrame(rows)
