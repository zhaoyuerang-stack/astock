"""workflow/promote 的 Nine-Gate 自动触发测试。

Run:
  cd /Users/kiki/astcok/factor_research && python3 tests/test_promote_nine_gate.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def test_promote_spec_runs_nine_gate_after_registered():
    import workflow.phase1_synthetic as phase1
    import workflow.phase2_backtest as phase2
    import workflow.phase3_wf as phase3
    import workflow.phase4_register as phase4
    import workflow.promote as promote
    from workflow.phase4_register import RegistrationReport

    old_phase1 = phase1.Phase1Checker
    old_phase2 = phase2.Phase2Runner
    old_phase3 = phase3.WF3Runner
    old_phase4 = phase4.Phase4Register
    calls: list[dict] = []

    class FakePhase1Checker:
        def __init__(self, *args, **kwargs):
            pass

        def run_all(self, use_clean=True, save_lessons=False):
            return []

    class FakePhase2Runner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, warmup_start="2010-01-01"):
            return {"segments": {}, "config": {}}

    class FakeWF3Runner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, warmup_start="2010-01-01"):
            return {"aggregate": {"verdict": "PASS"}}

    class FakePhase4Register:
        def __init__(self, family, version="v1.0"):
            self.family = family
            self.version = version

        def register(self, *args, **kwargs):
            return RegistrationReport(
                family=self.family,
                version=self.version,
                registered=True,
                repro_meta={},
                lessons_saved=0,
                detail="registered",
            )

    def fake_nine_gate_runner(strategy_name, n_trials=15, persist=False, version=None, start=None):
        calls.append({
            "strategy_name": strategy_name,
            "n_trials": n_trials,
            "persist": persist,
            "version": version,
            "start": start,
        })

    try:
        phase1.Phase1Checker = FakePhase1Checker
        phase2.Phase2Runner = FakePhase2Runner
        phase3.WF3Runner = FakeWF3Runner
        phase4.Phase4Register = FakePhase4Register

        spec = SimpleNamespace(
            name="small-cap-size",
            factor_builder=lambda *args, **kwargs: None,
            timing_builder=lambda *args, **kwargs: None,
            config={},
            hypothesis="test",
        )
        report = promote.promote_spec(
            spec,
            version="v-test",
            # 默认 run_nine_gate=True — 不显式传 True 也应触发
            nine_gate_runner=fake_nine_gate_runner,
        )

        assert report.registered is True
        assert calls == [{
            "strategy_name": "small_cap",
            "n_trials": 15,
            "persist": True,
            "version": "v-test",
            "start": None,
        }]
    finally:
        phase1.Phase1Checker = old_phase1
        phase2.Phase2Runner = old_phase2
        phase3.WF3Runner = old_phase3
        phase4.Phase4Register = old_phase4


def test_promote_spec_default_run_nine_gate_is_true():
    """审计#8: promote_spec 默认必须跑 9-Gate,禁止默认堆无 DSR 候选。"""
    import inspect
    import workflow.promote as promote

    sig = inspect.signature(promote.promote_spec)
    assert sig.parameters["run_nine_gate"].default is True


def test_promote_spec_explicit_false_skips_nine_gate():
    """显式 False 仍可跳过(调试);自动/CLI 入口另由守卫禁止字面 False。"""
    import workflow.phase1_synthetic as phase1
    import workflow.phase2_backtest as phase2
    import workflow.phase3_wf as phase3
    import workflow.phase4_register as phase4
    import workflow.promote as promote
    from workflow.phase4_register import RegistrationReport

    old_phase1 = phase1.Phase1Checker
    old_phase2 = phase2.Phase2Runner
    old_phase3 = phase3.WF3Runner
    old_phase4 = phase4.Phase4Register
    calls: list[dict] = []

    class FakePhase1Checker:
        def __init__(self, *args, **kwargs):
            pass

        def run_all(self, use_clean=True, save_lessons=False):
            return []

    class FakePhase2Runner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, warmup_start="2010-01-01"):
            return {"segments": {}, "config": {}}

    class FakeWF3Runner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, warmup_start="2010-01-01"):
            return {"aggregate": {"verdict": "PASS"}}

    class FakePhase4Register:
        def __init__(self, family, version="v1.0"):
            self.family = family
            self.version = version

        def register(self, *args, **kwargs):
            return RegistrationReport(
                family=self.family,
                version=self.version,
                registered=True,
                repro_meta={},
                lessons_saved=0,
                detail="registered",
            )

    def fake_nine_gate_runner(*args, **kwargs):
        calls.append(kwargs)
        return {"status": "PERSISTED"}

    try:
        phase1.Phase1Checker = FakePhase1Checker
        phase2.Phase2Runner = FakePhase2Runner
        phase3.WF3Runner = FakeWF3Runner
        phase4.Phase4Register = FakePhase4Register
        spec = SimpleNamespace(
            name="small-cap-size",
            factor_builder=lambda *args, **kwargs: None,
            timing_builder=lambda *args, **kwargs: None,
            config={},
            hypothesis="test",
        )
        promote.promote_spec(
            spec,
            version="v-skip-ng",
            run_nine_gate=False,
            nine_gate_runner=fake_nine_gate_runner,
        )
        assert calls == []
    finally:
        phase1.Phase1Checker = old_phase1
        phase2.Phase2Runner = old_phase2
        phase3.WF3Runner = old_phase3
        phase4.Phase4Register = old_phase4


def test_nine_gate_failure_is_attached_to_registry():
    import strategy_registry as registry
    import workflow.promote as promote
    from workflow.phase4_register import RegistrationReport

    old_registry = registry.REGISTRY
    registry.REGISTRY = Path(tempfile.mkdtemp()) / "strategy_versions.json"

    def failing_runner(*args, **kwargs):
        raise RuntimeError("nine-gate boom")

    try:
        registry.register_family("small-cap-size", "小盘成交额因子")
        # 本测试验 run_nine_gate_after_registration 把失败态写回台账,与 status 无关;
        # 登记为「候选」即可(ADR-020:在册 standalone 须 DSR,此处不涉准入轨)。
        registry.register(
            "small-cap-size",
            "v-fail",
            "test",
            config={},
            data_scope={},
            metrics={"annual": 0.30, "maxdd": -0.10},
            status="候选",
        )
        report = RegistrationReport(
            family="small-cap-size",
            version="v-fail",
            registered=True,
            repro_meta={},
            lessons_saved=0,
            detail="registered",
        )

        result = promote.run_nine_gate_after_registration(
            report,
            strategy_name="small_cap",
            runner=failing_runner,
        )

        version = registry._load()["families"][0]["versions"][0]
        assert result["status"] == "FAILED_TO_RUN"
        assert version["nine_gate"]["status"] == "FAILED_TO_RUN"
        assert version["nine_gate"]["strategy"] == "small_cap"
        assert "nine-gate boom" in version["nine_gate"]["error"]
    finally:
        registry.REGISTRY = old_registry


def test_promote_spec_skips_marginal_for_candidate_registration():
    import workflow.phase1_synthetic as phase1
    import workflow.phase2_backtest as phase2
    import workflow.phase3_wf as phase3
    import workflow.phase4_register as phase4
    import workflow.promote as promote
    from workflow.phase4_register import RegistrationReport

    old_phase1 = phase1.Phase1Checker
    old_phase2 = phase2.Phase2Runner
    old_phase3 = phase3.WF3Runner
    old_phase4 = phase4.Phase4Register
    old_run_marginal = promote._run_marginal
    calls: list[str] = []

    class FakePhase1Checker:
        def __init__(self, *args, **kwargs):
            pass

        def run_all(self, use_clean=True, save_lessons=False):
            return []

    class FakePhase2Runner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, warmup_start="2010-01-01"):
            return {"segments": {}, "config": {}}

    class FakeWF3Runner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, warmup_start="2010-01-01"):
            return {"aggregate": {"verdict": "FAIL"}}

    class FakePhase4Register:
        def __init__(self, family, version="v1.0"):
            self.family = family
            self.version = version

        def register(self, *args, **kwargs):
            return RegistrationReport(
                family=self.family,
                version=self.version,
                registered=True,
                repro_meta={},
                lessons_saved=0,
                detail="registered as candidate",
                status="候选",
            )

    def fake_run_marginal(*args, **kwargs):
        calls.append("called")

    try:
        phase1.Phase1Checker = FakePhase1Checker
        phase2.Phase2Runner = FakePhase2Runner
        phase3.WF3Runner = FakeWF3Runner
        phase4.Phase4Register = FakePhase4Register
        promote._run_marginal = fake_run_marginal

        spec = SimpleNamespace(
            name="small-cap-size",
            factor_builder=lambda *args, **kwargs: None,
            timing_builder=lambda *args, **kwargs: None,
            config={},
            hypothesis="test",
        )
        # 本测只关心 marginal 对「候选」跳过;9-Gate 用 no-op runner,避免默认 True 打到真数据
        report = promote.promote_spec(
            spec,
            version="v-candidate",
            run_marginal=True,
            nine_gate_runner=lambda *a, **k: {"status": "PERSISTED"},
        )

        assert report.registered is True
        assert report.status == "候选"
        assert calls == []
    finally:
        phase1.Phase1Checker = old_phase1
        phase2.Phase2Runner = old_phase2
        phase3.WF3Runner = old_phase3
        phase4.Phase4Register = old_phase4
        promote._run_marginal = old_run_marginal


def test_factory_cli_promote_hardcodes_run_nine_gate_true():
    """对抗: factory_cli.cmd_promote 必须字面 run_nine_gate=True,不得省略依赖易变默认。"""
    src = (ROOT / "apps" / "factory_cli.py").read_text(encoding="utf-8")
    assert "run_nine_gate=True" in src
    assert "run_nine_gate=False" not in src


def test_guard_flags_run_nine_gate_false():
    from scripts.ci.check_no_force_promote import scan_source

    src = "promote_pool_l3(version='v1.0', run_nine_gate=False)\n"
    v = scan_source(src, "x")
    assert len(v) == 1 and "run_nine_gate=False" in v[0]


if __name__ == "__main__":
    test_promote_spec_runs_nine_gate_after_registered()
    print("✅ test_promote_spec_runs_nine_gate_after_registered")
    test_promote_spec_default_run_nine_gate_is_true()
    print("✅ test_promote_spec_default_run_nine_gate_is_true")
    test_promote_spec_explicit_false_skips_nine_gate()
    print("✅ test_promote_spec_explicit_false_skips_nine_gate")
    test_nine_gate_failure_is_attached_to_registry()
    print("✅ test_nine_gate_failure_is_attached_to_registry")
    test_promote_spec_skips_marginal_for_candidate_registration()
    print("✅ test_promote_spec_skips_marginal_for_candidate_registration")
    test_factory_cli_promote_hardcodes_run_nine_gate_true()
    print("✅ test_factory_cli_promote_hardcodes_run_nine_gate_true")
    test_guard_flags_run_nine_gate_false()
    print("✅ test_guard_flags_run_nine_gate_false")
