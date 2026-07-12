"""Optional OpenBB provider adapter for global data probes.

OpenBB is intentionally imported lazily.  The repository must remain usable
without the package or provider credentials installed.
"""
from __future__ import annotations

import importlib
import os
from datetime import datetime, time, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd

from lake.global_catalog import DatasetSpec, SourceSpec


class ProviderUnavailable(RuntimeError):
    """Provider package or credentials are not available in this environment."""


class OpenBBGlobalProvider:
    provider = "openbb"

    def __init__(
        self,
        *,
        importer: Callable[[str], Any] | None = None,
        api_key_envs: dict[str, str] | None = None,
        source: SourceSpec | None = None,
    ) -> None:
        self._importer = importer or importlib.import_module
        self.api_key_envs = dict(api_key_envs or {})
        self.source = source

    def _load_obb(self) -> Any:
        module = self._importer("openbb")
        return getattr(module, "obb", module)

    def _credential_status(self) -> tuple[bool, str]:
        missing = [
            env
            for env in self.api_key_envs.values()
            if env and not os.environ.get(env)
        ]
        if missing:
            return False, f"missing API key env: {','.join(sorted(missing))}"
        return True, ""

    def probe(self, spec: DatasetSpec) -> dict:
        try:
            self._load_obb()
        except ModuleNotFoundError as exc:
            return {
                "ok": False,
                "provider": self.provider,
                "dataset_id": spec.dataset_id,
                "status": "provider_unavailable",
                "error": str(exc),
            }
        except Exception as exc:  # noqa: BLE001 - probe should be reportable, not fatal.
            return {
                "ok": False,
                "provider": self.provider,
                "dataset_id": spec.dataset_id,
                "status": "provider_unavailable",
                "error": f"{type(exc).__name__}: {exc}",
            }

        creds_ok, error = self._credential_status()
        if not creds_ok:
            return {
                "ok": False,
                "provider": self.provider,
                "dataset_id": spec.dataset_id,
                "status": "missing_credentials",
                "error": error,
            }
        if self.source and spec.dataset_id == "derivatives_daily":
            return {
                "ok": False,
                "provider": self.provider,
                "dataset_id": spec.dataset_id,
                "status": "historical_date_unverified",
                "error": "CBOE options chains currently ignore requested historical dates; historical PIT ingestion is blocked",
            }
        return {
            "ok": True,
            "provider": self.provider,
            "dataset_id": spec.dataset_id,
            "status": "available",
            "error": "",
        }

    def fetch(self, spec: DatasetSpec, *, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        status = self.probe(spec)
        if not status.get("ok"):
            raise ProviderUnavailable(status.get("error") or status.get("status") or "provider unavailable")
        if self.source is None:
            raise ProviderUnavailable("OpenBB fetch requires a concrete source admission record")
        if spec.dataset_id not in self.source.datasets:
            raise ProviderUnavailable(f"{self.source.source_id} is not admitted for {spec.dataset_id}")
        if spec.dataset_id == "derivatives_daily":
            raise ProviderUnavailable(
                "CBOE options chains currently ignore requested historical dates; historical PIT ingestion is blocked"
            )
        if spec.dataset_id not in {"market_price_daily", "etf_daily", "fx_daily", "commodity_daily"}:
            raise ProviderUnavailable(f"OpenBB fetch mapping is not configured for dataset_id={spec.dataset_id}")
        return self._fetch_prices(spec, start=start, end=end)

    @staticmethod
    def _provider_symbol(symbol: str, *, dataset_id: str) -> str:
        if dataset_id == "fx_daily":
            return symbol if symbol.endswith("=X") else f"{symbol}=X"
        return symbol

    @staticmethod
    def _date_column(frame: pd.DataFrame) -> str:
        for column in ("date", "datetime", "timestamp", "index"):
            if column in frame.columns:
                return column
        raise ProviderUnavailable("OpenBB historical response is missing a date index")

    def _fetch_prices(
        self,
        spec: DatasetSpec,
        *,
        start: str | None,
        end: str | None,
    ) -> pd.DataFrame:
        if not start:
            raise ProviderUnavailable("initial yfinance history fetch requires an explicit start date")
        symbols = self.source.allowlist_for(spec.dataset_id)
        if not symbols:
            raise ProviderUnavailable(f"{self.source.source_id} has no allowlist for {spec.dataset_id}")
        is_cboe = self.source.source_id == "global_cboe_us_price_v1"
        provider_symbols = list(symbols) if is_cboe else [self._provider_symbol(symbol, dataset_id=spec.dataset_id) for symbol in symbols]
        obb = self._load_obb()
        # Fetch one symbol at a time. yfinance's bulk endpoint may report an
        # empty aggregate response while obscuring which symbol failed; a
        # canonical batch must never be written with unknown coverage.
        frames: list[pd.DataFrame] = []
        for provider_symbol in provider_symbols:
            kwargs = {
                "symbol": provider_symbol,
                "provider": "cboe" if is_cboe else "yfinance",
                "start_date": start,
                "end_date": end,
            }
            if spec.dataset_id == "fx_daily":
                response = obb.currency.price.historical(**kwargs)
            elif is_cboe:
                response = obb.equity.price.historical(**kwargs)
            else:
                # yfinance does not expose an unadjusted historical price mode via
                # OpenBB. Keep the provider's split-adjusted series explicit.
                response = obb.equity.price.historical(**kwargs, adjustment="splits_only")
            item = response.to_df().reset_index()
            if item.empty:
                raise ProviderUnavailable(f"yfinance returned no rows for {provider_symbol}")
            if "symbol" not in item.columns:
                item["symbol"] = provider_symbol
            frames.append(item)
        frame = pd.concat(frames, ignore_index=True, sort=False)
        if frame.empty:
            raise ProviderUnavailable(f"yfinance returned no rows for {spec.dataset_id}")
        date_column = self._date_column(frame)
        reverse_symbols = dict(zip(provider_symbols, symbols, strict=True))
        frame["symbol"] = frame["symbol"].astype(str).map(reverse_symbols).fillna(frame["symbol"].astype(str))
        for column in ("open", "high", "low", "close"):
            if column not in frame.columns:
                raise ProviderUnavailable(f"yfinance response missing {column}")
        if "volume" not in frame.columns:
            frame["volume"] = 0.0

        dates = pd.to_datetime(frame[date_column], errors="coerce", utc=True)
        if dates.isna().any():
            raise ProviderUnavailable("yfinance response contains invalid date values")
        session_dates = dates.dt.tz_localize(None).dt.normalize()
        start_day = pd.Timestamp(start).normalize()
        end_day = pd.Timestamp(end).normalize() if end else None
        in_range = session_dates.ge(start_day)
        if end_day is not None:
            in_range &= session_dates.le(end_day)
        frame = frame.loc[in_range].copy()
        session_dates = session_dates.loc[in_range]
        if frame.empty:
            raise ProviderUnavailable(f"yfinance returned no rows in requested range for {spec.dataset_id}")
        received = set(frame["symbol"].astype(str))
        missing = sorted(set(symbols) - received)
        if missing:
            raise ProviderUnavailable(f"yfinance response missing allowlist symbols: {','.join(missing)}")
        local_zone = ZoneInfo(self.source.timezone)
        session_end = [
            datetime.combine(value.date(), time(23, 59, 59), tzinfo=local_zone).astimezone(timezone.utc)
            for value in session_dates
        ]
        exchange = {
            "market_price_daily": "YFINANCE_US",
            "etf_daily": "YFINANCE_US",
            "fx_daily": "YFINANCE_FX",
            "commodity_daily": "YFINANCE_FUTURES",
        }[spec.dataset_id]
        out = pd.DataFrame({
            "symbol": frame["symbol"].astype(str),
            "exchange": "CBOE_US" if is_cboe else exchange,
            "session_date": session_dates,
            # The source has only a date-level timestamp; this is deliberately
            # later than the unknown source close, never an asserted close time.
            "session_close_at": session_end,
            "available_at": session_end,
            "open": pd.to_numeric(frame["open"], errors="coerce"),
            "high": pd.to_numeric(frame["high"], errors="coerce"),
            "low": pd.to_numeric(frame["low"], errors="coerce"),
            "close": pd.to_numeric(frame["close"], errors="coerce"),
            "volume": pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0),
            "is_adjusted": True,
            "adjustment_version": "cboe_eod_research_v1" if is_cboe else "yfinance_splits_only_v1",
            "currency": self.source.currency,
        })
        return out
