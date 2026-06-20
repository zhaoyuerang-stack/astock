"""证据链闭合测试 — registry 版本须锚定 hypothesis_id + L0-L3 实验 ID。

Run:  cd /Users/kiki/astcok/factor_research && python3 tests/test_evidence_chain.py

覆盖:
1. register() 把 evidence 写进版本记录(向后兼容:省略 → 空 dict)。
2. Phase4Register.register() 把 hypothesis_id / evidence_experiment_ids 透传进台账。

全程用临时台账文件,绝不写脏真实 strategy_versions.json。
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import strategy_registry as reg
from workflow.phase4_register import Phase4Register


def _with_tmp_registry(fn):
    """把 reg.REGISTRY 临时重定向到空文件,跑完恢复。"""
    orig = reg.REGISTRY
    reg.REGISTRY = Path(tempfile.mktemp(suffix=".json"))
    try:
        fn()
    finally:
        reg.REGISTRY = orig


def _versions(family_id):
    fam = next(f for f in reg._load()["families"] if f["id"] == family_id)
    return fam["versions"]


def test_register_persists_evidence():
    def body():
        reg.register_family("fam-a", "测试家族")
        reg.register(
            "fam-a", "v1.0", "desc", config={}, data_scope={}, metrics={},
            evidence={"hypothesis_id": "abc12345def", "experiment_ids": ["e1", "e2"]},
        )
        v = _versions("fam-a")[0]
        assert v["evidence"]["hypothesis_id"] == "abc12345def"
        assert v["evidence"]["experiment_ids"] == ["e1", "e2"]
    _with_tmp_registry(body)
    print("✅ test_register_persists_evidence passed")


def test_register_evidence_defaults_empty():
    def body():
        reg.register_family("fam-b", "测试家族")
        reg.register("fam-b", "v1.0", "desc", config={}, data_scope={}, metrics={})
        assert _versions("fam-b")[0]["evidence"] == {}
    _with_tmp_registry(body)
    print("✅ test_register_evidence_defaults_empty passed")


def test_phase4_threads_evidence_into_registry():
    """Phase4Register.register() 把 hypothesis_id + 实验 ID 透传进台账。"""
    def body():
        p1 = []  # 无 phase1 check → 不 blocked
        p2 = {
            "config": {"top_n": 25},
            "segments": {
                "IS  2018-2022": {"annual": 0.20, "maxdd": -0.10, "sharpe": 1.5, "calmar": 2.0},
                "OOS 2023-2026": {"annual": 0.18, "maxdd": -0.12, "sharpe": 1.3},
                "压力 2010-2017": {"annual": 0.15, "maxdd": -0.15, "sharpe": 1.0},
            },
        }
        p3 = {"aggregate": {"verdict": "PASS", "annual": 0.19, "maxdd": -0.11, "sharpe": 1.4}}

        report = Phase4Register("fam-c", "v1.0").register(
            p1, p2, p3,
            hypothesis="测试假设",
            hypothesis_id="hyp9999aaaa",
            evidence_experiment_ids=["exp_l0", "exp_l1", "exp_l3"],
        )
        assert report.registered, f"应登记成功: {report.detail}"
        v = _versions("fam-c")[0]
        assert v["evidence"]["hypothesis_id"] == "hyp9999aaaa"
        assert v["evidence"]["experiment_ids"] == ["exp_l0", "exp_l1", "exp_l3"]
    _with_tmp_registry(body)
    print("✅ test_phase4_threads_evidence_into_registry passed")


if __name__ == "__main__":
    print("Running evidence chain tests...\n")
    test_register_persists_evidence()
    test_register_evidence_defaults_empty()
    test_phase4_threads_evidence_into_registry()
    print("\n🎉 All evidence chain tests passed!")
