"""check_layer_deps 守卫回归测试。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci import check_layer_deps as guard


def test_scripts_ops_research_layer_imports_are_guarded(monkeypatch, tmp_path):
    """scripts/ops 默认按生产运维处理,新增研究层 import 必须被守卫拦住。"""
    rogue = tmp_path / "scripts" / "ops" / "rogue.py"
    rogue.parent.mkdir(parents=True)
    rogue.write_text("from factory.autoresearch import CandidateRepository\n", encoding="utf-8")

    monkeypatch.setattr(guard, "ROOT", tmp_path)

    assert guard.check() == 1


def test_services_read_cannot_import_action_layer(monkeypatch, tmp_path):
    """services/read 是只读入口,不得反向调用 services/actions。"""
    rogue = tmp_path / "services" / "read" / "rogue.py"
    rogue.parent.mkdir(parents=True)
    rogue.write_text("from services.actions.autoresearch import run_autoresearch_seeds\n", encoding="utf-8")

    monkeypatch.setattr(guard, "ROOT", tmp_path)

    assert guard.check() == 1


def test_workflow_cannot_import_research_scripts(monkeypatch, tmp_path):
    """workflow 是可复用库层,不得反向依赖 scripts/research CLI。"""
    rogue = tmp_path / "workflow" / "rogue.py"
    rogue.parent.mkdir(parents=True)
    rogue.write_text(
        "from scripts.research.run_nine_gates_all import run_evaluation\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(guard, "ROOT", tmp_path)

    assert guard.check() == 1


def test_api_router_cannot_read_runtime_artifacts_directly(monkeypatch, tmp_path):
    """api router 只能走 services/contracts,不得直接读取 data_lake/reports/signals/paper。"""
    rogue = tmp_path / "api" / "routers" / "rogue.py"
    rogue.parent.mkdir(parents=True)
    rogue.write_text(
        "\n".join([
            "from pathlib import Path",
            "ROOT = Path(__file__).resolve().parents[2]",
            "def endpoint():",
            "    return (ROOT / 'data_lake' / 'agent' / 'x.json').read_text()",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(guard, "ROOT", tmp_path)

    assert guard.check() == 1


def test_services_read_can_read_runtime_artifacts(monkeypatch, tmp_path):
    """services/read 是 artifact 读取边界,允许封装文件布局。"""
    allowed = tmp_path / "services" / "read" / "artifact_view.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text(
        "\n".join([
            "from pathlib import Path",
            "ROOT = Path(__file__).resolve().parents[2]",
            "def view():",
            "    return (ROOT / 'data_lake' / 'agent' / 'x.json').read_text()",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(guard, "ROOT", tmp_path)

    assert guard.check() == 0


def test_services_action_promote_must_use_job_or_action_guard(monkeypatch, tmp_path):
    """services/actions 中触发晋级或台账动作,必须经 jobs/action_guard 接缝。"""
    rogue = tmp_path / "services" / "actions" / "rogue_promote.py"
    rogue.parent.mkdir(parents=True)
    rogue.write_text(
        "\n".join([
            "from workflow.promote import promote_hypothesis",
            "def run(hyp):",
            "    return promote_hypothesis(hyp, version='v1.0')",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(guard, "ROOT", tmp_path)

    assert guard.check() == 1


def test_api_runtime_artifact_write_requires_action_guard(monkeypatch, tmp_path):
    """api 层如需写运行审计产物,必须显式走 action_guard。"""
    rogue = tmp_path / "api" / "routers" / "rogue_settings.py"
    rogue.parent.mkdir(parents=True)
    rogue.write_text(
        "\n".join([
            "from pathlib import Path",
            "ROOT = Path(__file__).resolve().parents[2]",
            "AUDIT = ROOT / 'data_lake' / 'agent' / 'config_audit.jsonl'",
            "def save():",
            "    with AUDIT.open('a', encoding='utf-8') as f:",
            "        f.write('{}\\n')",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(guard, "ROOT", tmp_path)

    assert guard.check() == 1


def test_workflow_promote_has_no_research_script_allowlist():
    """A1 完成后 workflow/promote 不应再靠显式债务例外过关。"""
    assert (
        "workflow/promote.py",
        "scripts.research.run_nine_gates_all",
    ) not in guard.ALLOWED_IMPORT_EXCEPTIONS


def test_experiments_router_has_no_artifact_read_allowlist():
    """A2 完成后 experiments router 不应再靠 artifact 直读例外过关。"""
    assert "api/routers/experiments.py" not in guard.API_ARTIFACT_READ_ALLOWLIST


def test_live_repo_layer_deps_guard_passes():
    assert guard.check() == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
