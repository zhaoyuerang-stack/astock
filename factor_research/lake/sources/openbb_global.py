"""Optional OpenBB provider adapter for global data probes.

OpenBB is intentionally imported lazily.  The repository must remain usable
without the package or provider credentials installed.
"""
from __future__ import annotations

import importlib
import os
from typing import Any, Callable

import pandas as pd

from lake.global_catalog import DatasetSpec


class ProviderUnavailable(RuntimeError):
    """Provider package or credentials are not available in this environment."""


class OpenBBGlobalProvider:
    provider = "openbb"

    def __init__(
        self,
        *,
        importer: Callable[[str], Any] | None = None,
        api_key_envs: dict[str, str] | None = None,
    ) -> None:
        self._importer = importer or importlib.import_module
        self.api_key_envs = dict(api_key_envs or {})

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
        raise ProviderUnavailable(
            f"OpenBB fetch mapping is not configured for dataset_id={spec.dataset_id}; run probe first."
        )
