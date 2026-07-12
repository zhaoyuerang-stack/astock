"""Native FRED/ALFRED macro adapter with conservative vintage visibility."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import pandas as pd

from lake.global_catalog import DatasetSpec, SourceSpec
from lake.sources.openbb_global import ProviderUnavailable


FRED_BASE_URL = "https://api.stlouisfed.org/fred"
_FRED_EARLIEST_REALTIME = "1776-07-04"
_FRED_LATEST_REALTIME = "9999-12-31"
# FRED observations reject requests spanning more than 2,000 vintage dates.
# Four calendar years stay well below that ceiling while retaining every
# available vintage rather than silently falling back to latest-only values.
_MAX_REALTIME_WINDOW_DAYS = 365 * 4


def _frequency(value: str) -> str:
    lookup = {"D": "daily", "W": "weekly", "BW": "biweekly", "M": "monthly", "Q": "quarterly", "A": "annual"}
    return lookup.get(str(value).upper(), str(value).lower())


class AlfredMacroProvider:
    """Fetch raw FRED observations plus the ALFRED real-time interval fields.

    FRED real-time metadata is date-granular, not an intraday release timestamp.
    ``available_at`` is therefore conservatively set to the end of that source
    day in America/Chicago.  This can delay research signals but cannot expose
    them before the known vintage date.
    """

    provider = "alfred"

    def __init__(
        self,
        *,
        source: SourceSpec,
        environ: Mapping[str, str] | None = None,
        request_json: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
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
            "availability_confidence": self.source.availability_confidence,
        }

    def _request(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        if self._request_json is not None:
            return self._request_json(path, params)
        url = f"{FRED_BASE_URL}{path}?{urlencode(params)}"
        with urlopen(url, timeout=self.timeout_seconds) as response:  # noqa: S310 - fixed official endpoint.
            return json.loads(response.read().decode("utf-8"))

    def _series_metadata(self, series_id: str) -> dict[str, Any]:
        payload = self._request(
            "/series",
            {
                "series_id": series_id,
                "api_key": self._api_key,
                "file_type": "json",
                "realtime_start": _FRED_EARLIEST_REALTIME,
                "realtime_end": _FRED_LATEST_REALTIME,
            },
        )
        series = payload.get("seriess") or []
        if not series:
            raise ProviderUnavailable(f"FRED metadata missing for series_id={series_id}")
        return dict(series[0])

    @staticmethod
    def _realtime_windows(start: str) -> list[tuple[str, str]]:
        """Split the real-time vintage range into FRED-safe windows."""
        try:
            cursor = date.fromisoformat(start)
        except ValueError as exc:
            raise ProviderUnavailable(f"invalid observation start date: {start}") from exc
        latest = date.today()
        if cursor > latest:
            return []

        windows = []
        while cursor <= latest:
            window_end = min(cursor + timedelta(days=_MAX_REALTIME_WINDOW_DAYS - 1), latest)
            windows.append((cursor.isoformat(), window_end.isoformat()))
            cursor = window_end + timedelta(days=1)
        return windows

    def _observations(
        self,
        series_id: str,
        *,
        start: str,
        end: str | None,
        realtime_start: str,
        realtime_end: str,
    ) -> list[dict[str, Any]]:
        params = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "units": "lin",
            "sort_order": "asc",
            "limit": "100000",
        }
        params["observation_start"] = start
        if end:
            params["observation_end"] = end
        payload = self._request("/series/observations", params)
        return [dict(observation) for observation in payload.get("observations") or []]

    def _available_at(self, vintage_start: str) -> str:
        try:
            source_day = datetime.fromisoformat(vintage_start).date()
        except ValueError as exc:
            raise ProviderUnavailable(f"invalid FRED realtime_start: {vintage_start}") from exc
        local = datetime.combine(source_day, time(23, 59, 59), tzinfo=ZoneInfo(self.source.timezone))
        return local.astimezone(timezone.utc).isoformat(timespec="seconds")

    def fetch(self, spec: DatasetSpec, *, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        status = self.probe(spec)
        if not status.get("ok"):
            raise ProviderUnavailable(status.get("error") or status.get("status") or "provider unavailable")
        if not start:
            raise ProviderUnavailable("initial FRED/ALFRED history fetch requires an explicit start date")
        rows: list[dict[str, Any]] = []
        for series_id in self.source.allowlist_for(spec.dataset_id):
            metadata = self._series_metadata(series_id)
            for realtime_start, realtime_end in self._realtime_windows(start):
                for observation in self._observations(
                    series_id,
                    start=start,
                    end=end,
                    realtime_start=realtime_start,
                    realtime_end=realtime_end,
                ):
                    vintage_start = str(observation.get("realtime_start") or "")
                    rows.append({
                        "series_id": series_id,
                        "observation_date": observation.get("date"),
                        "value": observation.get("value"),
                        "unit": metadata.get("units"),
                        "frequency": _frequency(str(metadata.get("frequency_short") or metadata.get("frequency") or "")),
                        "vintage_start": vintage_start,
                        "vintage_end": observation.get("realtime_end"),
                        "available_at": self._available_at(vintage_start),
                    })
        return pd.DataFrame(rows)
