"""check_factor_registry 守卫 + factors.registry 注册门 对抗回归测试。

对抗性验收(护栏 C):每条断言先证明"坏东西真的被拒",再证明真实仓库现状通过。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci import check_factor_registry as guard
from factors.registry import FACTOR_REGISTRY, register_factor


# ── 注册门:import 期 fail-closed ─────────────────────────────────────────

def test_register_rejects_empty_definition():
    with pytest.raises(ValueError, match="definition 必填"):
        register_factor("_t_no_def", definition="  ")


def test_register_rejects_searchable_without_evidence():
    with pytest.raises(ValueError, match="evidence"):
        register_factor("_t_no_evidence", definition="x", searchable=True)


def test_register_rejects_same_name_different_source():
    @register_factor("_t_collision", definition="第一版")
    def fa(close):
        return close * 1.0

    try:
        with pytest.raises(ValueError, match="同名因子已注册且源码不同"):
            @register_factor("_t_collision", definition="第二版")
            def fb(close):
                return close * 2.0
    finally:
        FACTOR_REGISTRY.pop("_t_collision", None)


def test_register_records_definition_and_source_hash():
    @register_factor("_t_meta", definition="口径说明", evidence="probe:x")
    def fc(close):
        return close

    try:
        rec = FACTOR_REGISTRY["_t_meta"]
        assert rec.definition == "口径说明"
        assert len(rec.source_hash) == 12
    finally:
        FACTOR_REGISTRY.pop("_t_meta", None)


# ── C1:手工接线冻结(双向) ──────────────────────────────────────────────

def _surfaces_with(surface: str, keys: set):
    base = {k: set(v) for k, v in guard.LEGACY_HANDWIRED.items()}
    base[surface] = keys
    return base


def test_c1_new_handwired_entry_fails():
    keys = set(guard.LEGACY_HANDWIRED["dsl"]) | {"rogue_new_factor"}
    errors = guard.check_handwired_frozen(_surfaces_with("dsl", keys))
    assert any("rogue_new_factor" in e and "@register_factor" in e for e in errors)


def test_c1_stale_legacy_entry_fails():
    keys = set(guard.LEGACY_HANDWIRED["whitelist"]) - {"momentum"}
    errors = guard.check_handwired_frozen(_surfaces_with("whitelist", keys))
    assert any("momentum" in e and "LEGACY" in e for e in errors)


# ── C2:注册表完整性 ─────────────────────────────────────────────────────

def _rec(name, definition="ok", searchable=False, evidence="", source_hash=None):
    if source_hash is None:
        source_hash = ("h_" + name)[:12].ljust(12, "0")
    return SimpleNamespace(name=name, definition=definition, searchable=searchable,
                           evidence=evidence, source_hash=source_hash)


def test_c2_missing_definition_fails():
    errors = guard.check_registry_integrity({"f1": _rec("f1", definition="")})
    assert any("definition 为空" in e for e in errors)


def test_c2_searchable_without_evidence_fails():
    errors = guard.check_registry_integrity({"f1": _rec("f1", searchable=True)})
    assert any("evidence" in e for e in errors)


def test_c2_duplicate_source_hash_fails():
    reg = {"fa": _rec("fa", source_hash="deadbeef0001"),
           "fb": _rec("fb", source_hash="deadbeef0001")}
    errors = guard.check_registry_integrity(reg)
    assert any("source_hash" in e and "n_trials" in e for e in errors)


# ── C3:注册名与手工条目撞名 ─────────────────────────────────────────────

def test_c3_collision_fails():
    reg = {"holdertrade_net": _rec("holdertrade_net")}
    errors = guard.check_name_collision(reg, {k: set(v) for k, v in guard.LEGACY_HANDWIRED.items()})
    assert any("holdertrade_net" in e and "撞名" in e for e in errors)


def test_c3_no_collision_passes():
    reg = {"fresh_name": _rec("fresh_name")}
    assert guard.check_name_collision(
        reg, {k: set(v) for k, v in guard.LEGACY_HANDWIRED.items()}) == []


# ── C4:死模块处置标记(双向) ────────────────────────────────────────────

def _fake_repo(tmp_path: Path, dead_text: str, consumer_text: str | None = None) -> Path:
    (tmp_path / "factors").mkdir()
    (tmp_path / "factors" / "dead.py").write_text(dead_text, encoding="utf-8")
    if consumer_text is not None:
        (tmp_path / "strategies").mkdir()
        (tmp_path / "strategies" / "user.py").write_text(consumer_text, encoding="utf-8")
    return tmp_path


def test_c4_zero_consumer_without_tag_fails(tmp_path):
    root = _fake_repo(tmp_path, '"""死模块,无标记"""\n')
    errors = guard.check_dispositions(root)
    assert any("dead.py" in e and "Disposition" in e for e in errors)


def test_c4_tag_with_consumer_fails(tmp_path):
    root = _fake_repo(tmp_path,
                      '"""x\n\nDisposition: dormant — 假死\n"""\n',
                      "from factors.dead import something\n")
    errors = guard.check_dispositions(root)
    assert any("dead.py" in e and "标记说谎" in e for e in errors)


def test_c4_honest_states_pass(tmp_path):
    root = _fake_repo(tmp_path,
                      '"""x\n\nDisposition: dormant — 真死,零消费者\n"""\n')
    (root / "factors" / "alive.py").write_text('"""活模块"""\n', encoding="utf-8")
    (root / "strategies").mkdir()
    (root / "strategies" / "user.py").write_text("from factors import alive\n", encoding="utf-8")
    assert guard.check_dispositions(root) == []


# ── 行为等价钉死:holder_count_chg 收编手工接线后 spec 逐位不变 ───────────

def test_holder_count_chg_spec_unchanged_after_migration():
    from factory.autoresearch.registry import ALLOWED_FACTORS
    spec = ALLOWED_FACTORS["holder_count_chg"]
    assert spec.params == {"window": (40, 240)}
    assert tuple(spec.data_dependencies) == ("holder/holdernumber",)

    from factors.autoresearch_dsl import _FACTOR_CALLS
    assert _FACTOR_CALLS["holder_count_chg"] == (
        "factors.shareholder", "holder_count_chg", {"window": "window"})

    from strategies.catalog import resolve_factor_builder
    assert resolve_factor_builder("holder_count_chg") is not None


# ── 真实仓库集成:守卫全绿 ───────────────────────────────────────────────

def test_live_repo_factor_registry_guard_passes():
    assert guard.check() == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
