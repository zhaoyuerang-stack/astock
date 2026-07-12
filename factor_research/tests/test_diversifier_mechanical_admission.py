"""diversifier「在册」机械门槛 + marginal_receipt 绑定。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import strategy_registry as sr
from governance.marginal import GOOD_RESID_SHARPE, REDUNDANT_CORR
from research_ledger.receipts import (
    MARGINAL_RECEIPT_KEY,
    build_marginal_receipt,
    diversifier_admission_with_receipt,
    verify_marginal_receipt_self_consistent,
)
from strategy_registry import (
    DIVERSIFIER_MAX_ABS_CORR,
    DIVERSIFIER_MIN_RESIDUAL_SHARPE,
    _validate_diversifier_admission,
)


def _receipt_adm(
    family: str = "f",
    version: str = "v1",
    *,
    rationale: str = "负相关分流",
    corr: float = -0.2,
    residual_sharpe: float = 0.8,
    run_id: str = "a" * 16,
    entry_hash: str = "b" * 64,
    **extra,
) -> dict:
    return diversifier_admission_with_receipt(
        family,
        version,
        rationale=rationale,
        corr_to_book=corr,
        residual_sharpe=residual_sharpe,
        run_id=run_id,
        entry_hash=entry_hash,
        **extra,
    )


def test_thresholds_align_with_marginal_module():
    assert DIVERSIFIER_MAX_ABS_CORR == REDUNDANT_CORR
    assert DIVERSIFIER_MIN_RESIDUAL_SHARPE == GOOD_RESID_SHARPE


def test_validate_accepts_mechanical_pass_with_receipt():
    _validate_diversifier_admission("f", "v1", _receipt_adm())


@pytest.mark.parametrize(
    "adm,needle",
    [
        ({"rationale": "", "corr_to_book": -0.1, "residual_sharpe": 0.8}, "rationale"),
        ({"rationale": "x", "residual_sharpe": 0.8}, "corr_to_book"),
        ({"rationale": "x", "corr_to_book": -0.1}, "residual_sharpe"),
        ({"rationale": "x", "corr_to_book": True, "residual_sharpe": 0.8}, "corr_to_book"),
        ({"rationale": "x", "corr_to_book": 0.85, "residual_sharpe": 0.9}, "corr_to_book"),
        ({"rationale": "x", "corr_to_book": 0.1, "residual_sharpe": 0.2}, "residual_sharpe"),
        ({
            "rationale": "x",
            "corr_to_book": -0.1,
            "residual_sharpe": 0.8,
            "evidence_status": "INVALIDATED_BY_COST_RESTATEMENT",
        }, "作废"),
    ],
)
def test_validate_rejects_rubber_stamp(adm, needle):
    with pytest.raises(ValueError, match=needle):
        _validate_diversifier_admission("f", "v1", adm)


def test_validate_rejects_missing_receipt():
    with pytest.raises(ValueError, match="marginal_receipt|收据"):
        _validate_diversifier_admission(
            "f", "v1",
            {"rationale": "x", "corr_to_book": -0.1, "residual_sharpe": 0.8},
        )


def test_validate_rejects_tampered_numbers_keeping_old_receipt():
    """对抗:改 corr/residual 但不重开收据 → 拒。"""
    adm = _receipt_adm(corr=-0.2, residual_sharpe=0.8)
    adm["residual_sharpe"] = 0.99  # 手改数字
    with pytest.raises(ValueError, match="marginal_sha256|不一致"):
        _validate_diversifier_admission("f", "v1", adm)


def test_validate_rejects_receipt_from_other_family():
    """对抗:把 A 的收据贴到 B → binding 失败。"""
    adm = _receipt_adm(family="famA", version="v1")
    with pytest.raises(ValueError, match="binding|身份"):
        _validate_diversifier_admission("famB", "v1", adm)


def test_verify_self_consistent_helper_reports_missing():
    errs = verify_marginal_receipt_self_consistent("f", "v1", {}, None)
    assert any("marginal_receipt" in e for e in errs)


def test_register_rejects_string_only_diversifier(tmp_path, monkeypatch):
    reg = tmp_path / "strategy_versions.json"
    reg.write_text('{"families":[]}', encoding="utf-8")
    monkeypatch.setattr(sr, "REGISTRY", reg)
    sr.register_family("fam", "t")
    with pytest.raises(ValueError, match="corr_to_book"):
        sr.register(
            "fam", "v1", "d", {}, {},
            {"annual": 0.05, "maxdd": -0.10},
            status="在册",
            admission={"track": "diversifier", "rationale": "看起来像分散"},
        )


def test_register_rejects_numbers_without_receipt(tmp_path, monkeypatch):
    reg = tmp_path / "strategy_versions.json"
    reg.write_text('{"families":[]}', encoding="utf-8")
    monkeypatch.setattr(sr, "REGISTRY", reg)
    sr.register_family("fam", "t")
    with pytest.raises(ValueError, match="收据|marginal_receipt"):
        sr.register(
            "fam", "v1", "d", {}, {},
            {"annual": 0.05, "maxdd": -0.10},
            status="在册",
            admission={
                "track": "diversifier",
                "rationale": "手填好看数",
                "corr_to_book": -0.5,
                "residual_sharpe": 1.5,
            },
        )


def test_register_accepts_mechanical_diversifier_with_receipt(tmp_path, monkeypatch):
    reg = tmp_path / "strategy_versions.json"
    reg.write_text('{"families":[]}', encoding="utf-8")
    monkeypatch.setattr(sr, "REGISTRY", reg)
    sr.register_family("fam", "t")
    adm = _receipt_adm("fam", "v1", corr=-0.12, residual_sharpe=0.65)
    tag = sr.register(
        "fam", "v1", "d", {}, {},
        {"annual": 0.05, "maxdd": -0.10},
        status="在册",
        admission=adm,
    )
    assert tag == "fam/v1"
    v = sr._load()["families"][0]["versions"][0]
    assert v["status"] == "在册"
    assert v["admission"]["corr_to_book"] == -0.12
    assert MARGINAL_RECEIPT_KEY in v["admission"]
    assert len(v["admission"][MARGINAL_RECEIPT_KEY]["binding_sha256"]) == 64


def test_build_receipt_recomputable():
    metrics = {"corr_to_book": -0.1, "residual_sharpe": 0.7}
    r1 = build_marginal_receipt("f", "v1", metrics, run_id="c" * 16, entry_hash="d" * 64)
    r2 = build_marginal_receipt("f", "v1", metrics, run_id="c" * 16, entry_hash="d" * 64)
    assert r1 == r2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
