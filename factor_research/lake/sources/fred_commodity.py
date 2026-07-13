"""FRED commodity spot adapter for second-source review."""
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


FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

_SERIES_SPECS = {
    "CL=F": {"series_id": "DCOILWTICO"},
    "BZ=F": {"series_id": "DCOILBRENTEU"},
    "NG=F": {"series_id": "DHHNGSP"},
}


class FredCommodityProvider:
    provider = "fredcommodity"

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
        query["api_key"] = self._api_key
        query["file_type"] = "json"
        url = f"{FRED_BASE_URL}?{urlencode(query)}"
        with urlopen(url, timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed official endpoint.
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _session_close_at(day: str) -> str:
        stamp = datetime.combine(datetime.fromisoformat(day).date(), time(23, 59, 59), tzinfo=timezone.utc)
        return stamp.isoformat(timespec="seconds")

    def fetch(self, spec: DatasetSpec, *, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        status = self.probe(spec)
        if not status.get("ok"):
            raise ProviderUnavailable(status.get("error") or status.get("status") or "provider unavailable")
        if spec.dataset_id != "commodity_daily":
            raise ProviderUnavailable(f"FRED commodity adapter is not configured for {spec.dataset_id}")
        if not start:
            raise ProviderUnavailable("initial FRED commodity history fetch requires an explicit start date")

        rows: list[dict[str, Any]] = []
        for canonical_symbol in self.source.allowlist_for(spec.dataset_id):
            mapped = _SERIES_SPECS.get(canonical_symbol) or {}
            if not mapped:
                raise ProviderUnavailable(f"no FRED series mapping for {canonical_symbol}")
            payload = self._request(
                {
                    "series_id": mapped["series_id"],
                    "observation_start": start,
                    "observation_end": end or "",
                }
            )
            observations = payload.get("observations") or []
            for item in observations:
                close = pd.to_numeric(item.get("value"), errors="coerce")
                if pd.isna(close):
                    continue
                day = str(item.get("date"))
                rows.append(
                    {
                        "symbol": canonical_symbol,
                        "exchange": "FRED_SPOT",
                        "session_date": pd.Timestamp(day).normalize(),
                        "session_close_at": self._session_close_at(day),
                        "available_at": self._session_close_at(day),
                        "open": pd.NA,
                        "high": pd.NA,
                        "low": pd.NA,
                        "close": close,
                        "volume": 0.0,
                        "is_adjusted": False,
                        "adjustment_version": "fred_spot_v1",
                        "currency": self.source.currency,
                    }
                )
        return pd.DataFrame(rows)
