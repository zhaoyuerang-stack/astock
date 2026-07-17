"""Holdout 守卫必须识别无论函数如何命名的直接金库访问。

守卫审计 #2:ISO 日期字面量泛化 + factory/workflow/services/actions 扫描面。
"""
import pytest

from scripts.ci.check_holdout_compliance import (
    scan_direct_holdout_access,
    scan_direct_holdout_dirs,
    main,
    EXPECTED_BOUNDARY,
)


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


def test_mid_vault_iso_date_rejected():
    """审计 #2 对抗:df[df.index >= "2025-06-01"] 老守卫抓不到,新守卫必红。"""
    source = '''
def peek(df):
    return df[df.index >= "2025-06-01"]
'''
    v = scan_direct_holdout_access(source, "peek.py")
    assert v, '>= "2025-06-01" 金库内日期必须被抓'
    assert any("holdout boundary" in m or ">=" in m for m in v)


def test_strict_before_boundary_allowed():
    """df[df.index < "2025-01-01"] 截断语义不变,必绿。"""
    source = '''
def search(df):
    return df[df.index < "2025-01-01"]
'''
    assert scan_direct_holdout_access(source, "search.py") == []


def test_pre_boundary_start_date_not_flagged():
    """起始日常量 "2018-01-01"(< boundary)不误报。"""
    source = '''
START = "2018-01-01"
def load(df):
    return df[df.index >= START]
'''
    assert scan_direct_holdout_access(source, "hist.py") == []


def test_exact_boundary_still_flagged():
    """精确 EXPECTED_BOUNDARY 字面量仍红(回归)。"""
    source = f'''
def peek(df):
    return df[df.index >= "{EXPECTED_BOUNDARY}"]
'''
    assert scan_direct_holdout_access(source, "x.py")


def test_factory_dir_is_scanned(tmp_path):
    """审计 #2 对抗:fixture 放在 factory/ 模拟路径下也必须被扫到。"""
    factory = tmp_path / "factory"
    factory.mkdir()
    evil = factory / "rogue_search.py"
    evil.write_text(
        'def rank(df):\n    return df[df.index >= "2025-06-01"]\n',
        encoding="utf-8",
    )
    # 合法截断对照
    (factory / "clean.py").write_text(
        'def rank(df):\n    return df[df.index < "2025-01-01"]\n',
        encoding="utf-8",
    )
    hits = scan_direct_holdout_dirs(tmp_path)
    rels = {rel for rel, _ in hits}
    assert "factory/rogue_search.py" in rels
    assert "factory/clean.py" not in rels
    assert main(tmp_path) == 1


def test_live_repo_clean_with_pending():
    """真实仓库:存量 PENDING + 配置锁 → 无新增即绿。"""
    assert main() == 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
