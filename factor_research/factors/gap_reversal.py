"""DEPRECATED shim — 实现已迁至 factors._deprecated.gap_reversal。

正式路径禁止依赖本模块(R-ARCH-005)。导入会发出 DeprecationWarning。
"""
from __future__ import annotations

import warnings

warnings.warn(
    "factors.gap_reversal is deprecated (R-ARCH-005); not on factory/catalog/DSL paths. "
    "Legacy code lives in factors._deprecated.gap_reversal.",
    DeprecationWarning,
    stacklevel=2,
)

from factors._deprecated.gap_reversal import *  # noqa: F401,F403
