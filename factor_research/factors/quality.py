"""DEPRECATED shim — 实现已迁至 factors._deprecated.quality。

正式路径禁止依赖本模块(R-ARCH-005)。导入会发出 DeprecationWarning。
"""
from __future__ import annotations

import warnings

warnings.warn(
    "factors.quality is deprecated (R-ARCH-005); use factors.fundamental for panel quality factors. "
    "Legacy helpers live in factors._deprecated.quality.",
    DeprecationWarning,
    stacklevel=2,
)

from factors._deprecated.quality import *  # noqa: F401,F403
