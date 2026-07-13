"""台账 small_cap_factor__window* 冗余簇标记守卫。

metasearch_findings_20260623: 6 窗口互 MI>2.0 同一信息源。
2026-07-12 处置: window60 为簇代表保留「候选」;其余 6 窗口降「参考」(不删历史)。

本测试读 canonical strategy_versions.json,防回滚成 7 个独立候选占位。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "strategy_versions.json"

# 与 mutate_existing 收敛后仍可能在台账遗留的历史窗口家族
_WINDOW_FAMILY_IDS = (
    "small_cap_factor__window20",
    "small_cap_factor__window30",
    "small_cap_factor__window45",
    "small_cap_factor__window60",
    "small_cap_factor__window90",
    "small_cap_factor__window120",
    "small_cap_factor__window252",
)
_REPRESENTATIVE = "small_cap_factor__window60"
# 非代表:不得再以「候选」占搜索/观察名额
_ALLOWED_NON_REPR_STATUS = frozenset({"参考", "退役", "已证伪", "REJECTED_BY_ADVERSARIAL_DECAY"})


def _load_families() -> dict[str, dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fams = data.get("families", data)
    if isinstance(fams, list):
        return {f["id"]: f for f in fams if isinstance(f, dict) and "id" in f}
    if isinstance(fams, dict):
        return fams
    raise AssertionError(f"unexpected strategy_versions schema: {type(fams)}")


def _version_statuses(fam: dict) -> list[tuple[str, str]]:
    vers = fam.get("versions") or []
    out = []
    if isinstance(vers, list):
        for v in vers:
            out.append((str(v.get("version")), str(v.get("status"))))
    elif isinstance(vers, dict):
        for vk, vv in vers.items():
            out.append((str(vk), str((vv or {}).get("status"))))
    return out


def test_window_cluster_families_exist():
    by_id = _load_families()
    missing = [fid for fid in _WINDOW_FAMILY_IDS if fid not in by_id]
    assert not missing, f"预期存在的 window 家族缺失: {missing}"


def test_representative_window60_remains_candidate():
    """簇代表须可继续观察(候选);不得被误降成与冗余成员同一处置而丢失入口。"""
    fam = _load_families()[_REPRESENTATIVE]
    statuses = _version_statuses(fam)
    assert statuses, f"{_REPRESENTATIVE} 无版本"
    # 至少一个版本为候选(允许同家族另有历史参考版)
    assert any(st == "候选" for _, st in statuses), (
        f"{_REPRESENTATIVE} 应保留至少一版「候选」,实际: {statuses}"
    )


def test_non_representative_windows_not_candidate():
    """非代表窗口不得再以「候选」占位(应 参考/退役/已证伪)。"""
    by_id = _load_families()
    bad: list[str] = []
    for fid in _WINDOW_FAMILY_IDS:
        if fid == _REPRESENTATIVE:
            continue
        fam = by_id[fid]
        for ver, st in _version_statuses(fam):
            if st == "候选":
                bad.append(f"{fid}/{ver} status={st}")
            elif st not in _ALLOWED_NON_REPR_STATUS:
                # 允许未知终态以外的,但「候选」是硬禁止;其它非预期状态也报告
                bad.append(f"{fid}/{ver} status={st!r} (期望 {_ALLOWED_NON_REPR_STATUS})")
    assert not bad, (
        "small_cap 多窗口簇标记被回滚或未完成:\n  " + "\n  ".join(bad)
    )


def test_non_representative_notes_mention_cluster():
    """非代表 notes 应留下簇标记审计线索(防 silent status 改回)。"""
    by_id = _load_families()
    weak: list[str] = []
    for fid in _WINDOW_FAMILY_IDS:
        if fid == _REPRESENTATIVE:
            continue
        for v in by_id[fid].get("versions") or []:
            notes = str(v.get("notes") or "")
            if "冗余" not in notes and "MI" not in notes and "簇" not in notes:
                weak.append(f"{fid}/{v.get('version')}: notes 缺簇标记线索")
    assert not weak, "参考版 notes 应含 MI/冗余/簇 审计字样:\n  " + "\n  ".join(weak)


if __name__ == "__main__":
    test_window_cluster_families_exist()
    test_representative_window60_remains_candidate()
    test_non_representative_windows_not_candidate()
    test_non_representative_notes_mention_cluster()
    print("ok")
