"""Task 17 / 审计 #7: 控制路径静默异常守卫 —— except:pass/continue/裸return 必被拒。"""
import pytest

from scripts.ci.check_control_exceptions import (
    scan_source,
    main,
    resolve_control_paths,
    ROOT,
)


def test_flags_bare_except_pass():
    src = "def f():\n    try:\n        x()\n    except Exception:\n        pass\n"
    assert scan_source(src, "x") != []


def test_flags_ellipsis_swallow():
    src = "def f():\n    try:\n        x()\n    except Exception:\n        ...\n"
    assert scan_source(src, "x") != []


def test_flags_except_continue():
    """审计 #7 对抗:except Exception: continue 必红。"""
    src = "def f():\n    for i in range(1):\n        try:\n            x()\n        except Exception:\n            continue\n"
    v = scan_source(src, "x")
    assert v != [], "except: continue 必须被抓"


def test_flags_bare_return():
    """审计 #7 对抗:except: return(裸,无值)必红。"""
    src = "def f():\n    try:\n        x()\n    except Exception:\n        return\n"
    v = scan_source(src, "x")
    assert v != [], "裸 return 必须被抓"


def test_allows_return_none_and_empty_dict():
    """边界:return None / return {} 不扩(可能合法 fail-closed)。"""
    src_none = "def f():\n    try:\n        x()\n    except Exception:\n        return None\n"
    src_dict = "def f():\n    try:\n        x()\n    except Exception:\n        return {}\n"
    assert scan_source(src_none, "x") == []
    assert scan_source(src_dict, "x") == []


def test_allows_logged_handler():
    """对抗:except Exception: log.warning(...) 必绿。"""
    src = ("def f():\n    try:\n        x()\n    except Exception as e:\n"
           "        log.warning(e)\n")
    assert scan_source(src, "x") == []


def test_allows_reraise_and_return_state():
    src = ("def f():\n    try:\n        x()\n    except Exception:\n        return 'BLOCKED'\n")
    assert scan_source(src, "x") == []


def test_docstring_then_pass_still_flagged():
    src = ('def f():\n    try:\n        x()\n    except Exception:\n        "noop"\n        pass\n')
    assert scan_source(src, "x") != []


def test_agent_control_surface_included():
    """ADR-037 控制面 services/agent/*.py 与 apps/agent_cli.py 必须在扫描清单。"""
    paths = resolve_control_paths()
    assert "apps/agent_cli.py" in paths
    agent_files = [p for p in paths if p.startswith("services/agent/")]
    assert len(agent_files) >= 5, f"services/agent 应 glob 纳入: {agent_files}"
    assert any(p.endswith("evidence.py") for p in agent_files)
    assert any(p.endswith("protocol_runner.py") for p in agent_files)


def test_new_agent_module_auto_included(tmp_path):
    """目录 glob:今后 services/agent/ 新增 .py 自动纳入,无需改清单。"""
    agent = tmp_path / "services" / "agent"
    agent.mkdir(parents=True)
    (agent / "brand_new.py").write_text("# future module\n", encoding="utf-8")
    paths = resolve_control_paths(tmp_path)
    assert "services/agent/brand_new.py" in paths


def test_repo_control_paths_have_no_new_silent_swallow():
    # 存量在 PENDING_REMEDIATION → 无新增即绿
    assert main() == 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
