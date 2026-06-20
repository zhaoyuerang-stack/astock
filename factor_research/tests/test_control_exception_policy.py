"""Task 17: 控制路径静默异常守卫 —— except:pass 必被拒。"""
import pytest

from scripts.ci.check_control_exceptions import scan_source, main


def test_flags_bare_except_pass():
    src = "def f():\n    try:\n        x()\n    except Exception:\n        pass\n"
    assert scan_source(src, "x") != []


def test_flags_ellipsis_swallow():
    src = "def f():\n    try:\n        x()\n    except Exception:\n        ...\n"
    assert scan_source(src, "x") != []


def test_allows_logged_handler():
    src = ("def f():\n    try:\n        x()\n    except Exception as e:\n"
           "        log.warning(e)\n")
    assert scan_source(src, "x") == []


def test_allows_reraise_and_return_state():
    src = ("def f():\n    try:\n        x()\n    except Exception:\n        return 'BLOCKED'\n")
    assert scan_source(src, "x") == []


def test_docstring_then_pass_still_flagged():
    src = ('def f():\n    try:\n        x()\n    except Exception:\n        "noop"\n        pass\n')
    assert scan_source(src, "x") != []


def test_repo_control_paths_have_no_silent_swallow():
    # 全仓控制路径必须 0 静默吞异常(回归守卫)
    assert main() == 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
