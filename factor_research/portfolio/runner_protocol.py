"""Minimal portfolio runner contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import pandas as pd


class StrategyRunner(Protocol):
    def __call__(self, start: str = "2018-01-01") -> pd.Series:
        """Return daily strategy returns."""


@dataclass(frozen=True)
class RunnerResult:
    name: str
    returns: pd.Series


RunnerFn = Callable[[str], pd.Series]
