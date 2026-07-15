"""Holdout 守卫必须识别无论函数如何命名的直接金库访问。"""
import pytest

from scripts.ci.check_holdout_compliance import scan_direct_holdout_access


@pytest.mark.parametrize(
    "source",
    [
        """
HOLDOUT_START = "2025-01-01"
def main(returns):
    return returns.loc[HOLDOUT_START:]
""",
        """
HOLDOUT_START = "2025-01-01"
def evaluate(returns):
    return evaluate_window(returns, HOLDOUT_START, None)
""",
        """
from governance.holdout import boundary
def report(returns):
    b = boundary()
    return returns.loc[returns.index >= b]
""",
        """
def report(returns):
    return returns.loc["2025-01-01":]
""",
        """
START = "2025-01-01"
def report(returns):
    return returns.loc[START:]
""",
        """
from governance.holdout import boundary
BOUNDARY = boundary()
START = BOUNDARY
def report(returns):
    return returns.loc[START:]
""",
        """
from governance.holdout import boundary
def report(returns):
    start = boundary()
    return evaluate_window(returns, start, None)
""",
    ],
)
def test_direct_holdout_access_is_rejected(source):
    assert scan_direct_holdout_access(source, "probe.py")


def test_search_window_truncated_before_boundary_is_allowed():
    source = """
from governance.holdout import boundary
def search(returns):
    b = boundary()
    return returns.loc[returns.index < b]
"""
    assert scan_direct_holdout_access(source, "search.py") == []
