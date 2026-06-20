"""台账 9-Gate 证据完整性守卫(防自欺)。

两道机械门(对应治理草稿 C.1 / C.3,源案见 illiquidity-large-cap 与 industry-neglect v1.3):
  G1 跨家族 IC 证据照抄:不同 family 的版本共享逐位相同的 IC 证据块 = 违规。
     (同 family 多版本共享 IC 合法——同因子同宇宙 IC 不该变。)
  G2 standalone 证据缺失/跳门:active 在册且 admission.track=standalone 的版本,
     - nine_gate 与 evidence 皆空 → 违规(无任何门禁证据就准入,绕过 9-Gate)。
     - passed_all=true 但必算门(dsr_p / pbo)为 None → 违规(跳门却标通过)。

只读 strategy_versions.json,违规则 exit 1。检测函数吃 dict,便于 fixture 测试。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "strategy_versions.json"

IC_KEYS = ["ic_mean", "nw_icir", "neut_nw_icir", "icir_retention",
           "monotonicity_corr", "ic_win_rate", "ic_decay"]
ACTIVE_STATUS = {"在册", "active", "APPROVED"}
REQUIRED_GATES = ["dsr_p", "pbo"]  # passed_all=true 时必须实算(非 None)

# 已知病灶基线(2026-06 回扫发现,grandfather 待 workflow 处置;**修复后须从此处移除**)。
# 守卫只对「新」违规 exit 1;下列项仅打印为待处置警告,不阻塞。处置清单见
# scratch/illiq_largecap_governance_DRAFT.md(退役/补审/降级)。
PENDING_REMEDIATION = {
    # G1 跨家族 IC 照抄:illiquidity-large-cap 盖了小盘 illiquidity 家族的 IC 章(独立重算 IC=−0.084)
    "G1:illiquidity,illiquidity-large-cap": "illiq-large-cap 退役/重分类后,其 IC 块不再跨家族",
    # G2 illiquidity-large-cap passed_all=true 却 pbo 未算
    "G2-skip:illiquidity-large-cap/v1.0:pbo": "同上,退役后消失",
    # G2 industry-neglect v1.3 证据全空绕过 9-Gate
    "G2-empty:industry-neglect-rotation/v1.3": "补独立 9-Gate(L2 复合 DSR/PBO)+ admission 标注后消失",
}


def extract_versions(ledger: dict) -> list[dict]:
    """展平为 [{family, version, status, track, nine_gate, evidence}]。"""
    fams: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("id") and "versions" in o:
                fams.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(ledger)
    rows = []
    for fam in fams:
        vers = fam["versions"]
        vers = vers if isinstance(vers, list) else list(vers.values())
        for v in vers:
            ng = v.get("nine_gate") or {}
            adm = v.get("admission") or {}
            rows.append({
                "family": fam["id"],
                "version": v.get("version"),
                "status": v.get("status") or fam.get("status"),
                "track": adm.get("track"),
                "nine_gate": ng,
                "evidence": v.get("evidence") or {},
            })
    return rows


def _ic_sig(ng: dict) -> str | None:
    sub = {k: ng.get(k) for k in IC_KEYS if k in ng}
    if not sub:
        return None
    return hashlib.md5(json.dumps(sub, sort_keys=True, default=str).encode()).hexdigest()[:12]


def find_cross_family_ic_copies(rows: list[dict]) -> list[tuple[str, str]]:
    """G1:同一 IC 块 hash 跨 >1 个 family = 照抄。返回 [(key, msg)]。"""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        sig = _ic_sig(r["nine_gate"])
        if sig is not None:
            groups.setdefault(sig, []).append(r)
    out = []
    for sig, members in groups.items():
        fams = sorted({m["family"] for m in members})
        if len(fams) > 1:
            who = ", ".join(f"{m['family']}/{m['version']}" for m in members)
            key = "G1:" + ",".join(fams)
            out.append((key, f"[G1 跨家族IC照抄] IC块#{sig} 被多个 family 共享: {who} — 须各宇宙独立重算"))
    return out


def find_standalone_evidence_gaps(rows: list[dict]) -> list[tuple[str, str]]:
    """G2:active standalone 的证据缺失 / 跳门却标通过。返回 [(key, msg)]。"""
    out = []
    for r in rows:
        if r["status"] not in ACTIVE_STATUS or r["track"] != "standalone":
            continue
        tag = f"{r['family']}/{r['version']}"
        ng = r["nine_gate"]
        if not ng and not r["evidence"]:
            out.append((f"G2-empty:{tag}",
                        f"[G2 证据全空] {tag} active+standalone 但 nine_gate 与 evidence 皆空 — 绕过 9-Gate 准入"))
            continue
        if ng.get("passed_all") is True:
            skipped = [g for g in REQUIRED_GATES if ng.get(g) is None]
            if skipped:
                out.append((f"G2-skip:{tag}:{','.join(skipped)}",
                            f"[G2 跳门标通过] {tag} passed_all=true 但 {','.join(skipped)} 未实算(None)"))
    return out


def check(ledger: dict | None = None) -> int:
    if ledger is None:
        ledger = json.loads(LEDGER.read_text())
    rows = extract_versions(ledger)
    all_v = find_cross_family_ic_copies(rows) + find_standalone_evidence_gaps(rows)
    keys = {k for k, _ in all_v}

    new_v = [(k, m) for k, m in all_v if k not in PENDING_REMEDIATION]
    pending = [(k, m) for k, m in all_v if k in PENDING_REMEDIATION]
    stale = [k for k in PENDING_REMEDIATION if k not in keys]  # 已修复但还挂在基线

    for k, m in pending:
        print(f"  ⚠️ 待处置(基线): {m}")
    for k in stale:
        print(f"  ℹ️ 基线项已修复,请从 PENDING_REMEDIATION 移除: {k}")

    if new_v:
        print("台账证据完整性检查发现【新】违规:")
        for k, m in new_v:
            print(f"  {m}")
        return 1
    print(f"台账证据完整性检查通过(无新违规;{len(pending)} 项待处置已基线)。")
    return 0


if __name__ == "__main__":
    sys.exit(check())
