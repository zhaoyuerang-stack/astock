"""台账 9-Gate 证据完整性守卫(防自欺)。

四道机械门(对应治理草稿 C.1 / C.3,源案见 illiquidity-large-cap 与 industry-neglect v1.3):
  G1 跨家族 IC 证据照抄:不同 family 的版本共享逐位相同或高度近似的 IC 证据块 = 违规。
     (同 family 多版本共享 IC 合法——同因子同宇宙 IC 不该变。)
  G2 standalone 证据缺失/跳门:active 在册且 admission.track=standalone 的版本,
     - nine_gate 与 evidence 皆空 → 违规(无任何门禁证据就准入,绕过 9-Gate)。
     - passed_all=true 但必算门(dsr_p / pbo)为 None → 违规(跳门却标通过)。
  G4 active standalone 的 Nine-Gate 证据必须携带结构化运行收据；收据把
     family/version、完整 nine_gate 摘要和 research-ledger run/entry 身份绑定在一起。
  G5 active diversifier 必须携带 marginal_receipt：把 corr_to_book/residual_sharpe
     与 family/version + research-ledger run/entry 绑定；禁止手填数字拆收据。

只读 strategy_versions.json,违规则 exit 1。检测函数吃 dict,便于 fixture 测试。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from research_ledger.receipts import (  # noqa: E402
    MARGINAL_RECEIPT_KEY,
    RECEIPT_KEY,
    build_nine_gate_receipt,
    canonical_hash as _canonical_hash,
    marginal_metrics_payload,
    marginal_receipt_binding as _marginal_receipt_binding,
    receipt_binding as _receipt_binding,
    verify_marginal_receipt_self_consistent,
)

LEDGER = PROJECT_ROOT / "strategy_versions.json"
RESEARCH_LEDGER = (
    PROJECT_ROOT / "data_lake" / "governance" / "research_ledger.jsonl"
)

IC_KEYS = ["ic_mean", "nw_icir", "neut_nw_icir", "icir_retention",
           "monotonicity_corr", "ic_win_rate", "ic_decay"]
ACTIVE_STATUS = {"在册", "active", "APPROVED"}
REQUIRED_GATES = ["dsr_p", "pbo"]  # passed_all=true 时必须实算(非 None)
DSR_ALPHA = 0.05  # standalone 准入要求 DSR 多重测试惩罚下显著(dsr_p<此值)；与 strategy_registry.DSR_ALPHA 对齐
NINE_GATE_SCRIPT = "scripts/research/run_nine_gates_all.py"
HEX_16 = re.compile(r"^[0-9a-f]{16}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
NEAR_COPY_MIN_POINTS = 4
NEAR_COPY_EXACT_RATIO = 0.80
NEAR_COPY_PATH_COVERAGE = 0.90

# 已知病灶基线(2026-06 回扫发现,grandfather 待 workflow 处置;**修复后须从此处移除**)。
# 守卫只对「新」违规 exit 1;下列项仅打印为待处置警告,不阻塞。处置清单见
# scratch/illiq_largecap_governance_DRAFT.md(退役/补审/降级)。
PENDING_REMEDIATION: dict[str, str] = {}
# 已修复并移除(ADR-017 处置,2026-06):
#   G1:illiquidity,illiquidity-large-cap —— illiq-large-cap/v1.0 已退役 + nine_gate 重写为
#       INVALIDATED_EVIDENCE_PLAGIARIZED,原照抄 IC 块归档于 evidence.archived_invalid_nine_gate。
#   G2-skip:illiquidity-large-cap/v1.0:pbo —— 同上,passed_all 已改 False,不再「跳门标通过」。
#   G2-empty:industry-neglect-rotation/v1.3 —— 补 L0/L1/L2 归因 nine_gate(passed_all=False,
#       DSR/PBO 因 trial_count_unknown 明确标 None,非伪造)+ evidence.admission_caveat 标注
#       standalone 资格实际靠 MA16 择时覆盖,裸因子不达标。


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
                "admission": adm if isinstance(adm, dict) else {},
                "nine_gate": ng,
                "evidence": v.get("evidence") or {},
            })
    return rows


def _ic_sig(ng: dict) -> str | None:
    sub = {k: ng.get(k) for k in IC_KEYS if k in ng}
    if not sub:
        return None
    return hashlib.sha256(
        json.dumps(sub, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()[:12]


def _numeric_leaves(value: Any, prefix: str = "") -> dict[str, float]:
    """提取 IC 块的有限数值叶子；路径保留结构，避免只比数值集合。"""
    if isinstance(value, bool):
        return {}
    if isinstance(value, (int, float)):
        number = float(value)
        return {prefix: number} if math.isfinite(number) else {}
    if isinstance(value, dict):
        out: dict[str, float] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.update(_numeric_leaves(child, child_prefix))
        return out
    if isinstance(value, (list, tuple)):
        out: dict[str, float] = {}
        for idx, child in enumerate(value):
            child_prefix = f"{prefix}[{idx}]"
            out.update(_numeric_leaves(child, child_prefix))
        return out
    return {}


def _numeric_ic_map(ng: dict) -> dict[str, float]:
    return _numeric_leaves({k: ng[k] for k in IC_KEYS if k in ng})


def _is_near_ic_copy(left: dict, right: dict) -> bool:
    """识别“整块复制后只微调极少数值”，并避免把正常相近结果判成复制。

    只有结构路径高度重合、至少 4 个数值点、80% 以上逐位完全相同，且剩余改动
    都只是相对/绝对小扰动时才命中。独立重算通常不会逐位共享这么多浮点数。
    """
    a = _numeric_ic_map(left)
    b = _numeric_ic_map(right)
    common = set(a) & set(b)
    if len(common) < NEAR_COPY_MIN_POINTS:
        return False
    coverage = len(common) / max(len(a), len(b))
    if coverage < NEAR_COPY_PATH_COVERAGE:
        return False
    exact = [path for path in common if a[path] == b[path]]
    changed = [path for path in common if a[path] != b[path]]
    if not changed or len(exact) / len(common) < NEAR_COPY_EXACT_RATIO:
        return False
    for path in changed:
        scale = max(abs(a[path]), abs(b[path]), 0.01)
        if abs(a[path] - b[path]) > max(1e-6, 0.10 * scale):
            return False
    return True


def find_cross_family_ic_copies(rows: list[dict]) -> list[tuple[str, str]]:
    """G1:同一/近似 IC 块跨 family = 照抄嫌疑。返回 [(key, msg)]。"""
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

    # 精确 hash 之外再做低误报的 pairwise 近似检测：防止只改最后一位小数绕过。
    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            if left["family"] == right["family"]:
                continue
            left_sig = _ic_sig(left["nine_gate"])
            right_sig = _ic_sig(right["nine_gate"])
            if left_sig is None or right_sig is None or left_sig == right_sig:
                continue
            if not _is_near_ic_copy(left["nine_gate"], right["nine_gate"]):
                continue
            fams = sorted((left["family"], right["family"]))
            key = "G1-near:" + ",".join(fams)
            who = f"{left['family']}/{left['version']}, {right['family']}/{right['version']}"
            out.append((
                key,
                f"[G1 跨家族IC近似复制] {who} 的 IC 路径高度重合且绝大多数浮点逐位相同，"
                "仅少数值有微扰 — 须提供各宇宙独立运行收据",
            ))
    return out


def _load_research_records(path: Path = RESEARCH_LEDGER) -> list[dict] | None:
    """Load and verify the immutable run ledger when the lake is present."""
    if not path.is_file():
        return None
    records: list[dict] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"research ledger line {lineno} JSON invalid: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"research ledger line {lineno} must be a JSON object")
        records.append(record)
    problems = research_chain_problems(records)
    if problems:
        raise ValueError("research ledger hash chain invalid: " + "; ".join(problems[:3]))
    return records


def _record_entry_hash(record: dict) -> str:
    """复算 research_ledger.ledger._chain_hash，不信任记录自报 entry_hash。"""
    payload = {k: v for k, v in record.items() if k not in ("prev_hash", "entry_hash")}
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return hashlib.sha256((str(record.get("prev_hash", "")) + payload_hash).encode("utf-8")).hexdigest()


def _record_run_id(record: dict) -> str:
    """复算 ResearchRunRecord.to_dict 的确定性 run_id。"""
    payload = json.dumps(
        {
            "script": record.get("script", ""),
            "hypothesis": record.get("hypothesis", ""),
            "run_at": record.get("run_at", ""),
            "source": record.get("source", ""),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def research_chain_problems(records: list[dict]) -> list[str]:
    """Verify continuity and every content hash, not just a referenced row."""
    problems: list[str] = []
    previous = ""
    for index, record in enumerate(records, 1):
        entry_hash = str(record.get("entry_hash") or "")
        if HEX_64.fullmatch(entry_hash) is None:
            problems.append(f"line {index} missing valid entry_hash")
            continue
        if str(record.get("prev_hash") or "") != previous:
            problems.append(f"line {index} prev_hash breaks chain")
        if _record_entry_hash(record) != entry_hash:
            problems.append(f"line {index} content hash mismatch")
        previous = entry_hash
    return problems


def find_nine_gate_receipt_gaps(
    rows: list[dict], research_records: list[dict] | None = None
) -> list[tuple[str, str]]:
    """G4:active standalone 必须有与身份、摘要和运行账本绑定的结构化收据。"""
    out: list[tuple[str, str]] = []
    record_index: dict[tuple[str, str], dict] = {}
    if research_records is not None:
        chain_problems = research_chain_problems(research_records)
        if chain_problems:
            return [
                (f"G4-ledger-chain:{index}", f"[G4 运行账本断链] {problem}")
                for index, problem in enumerate(chain_problems, 1)
            ]
        record_index = {
            (str(rec.get("run_id", "")), str(rec.get("entry_hash", ""))): rec
            for rec in research_records
            if rec.get("record_type") == "research_run"
        }

    for row in rows:
        if row["status"] not in ACTIVE_STATUS or row["track"] != "standalone":
            continue
        tag = f"{row['family']}/{row['version']}"
        receipt = row["evidence"].get(RECEIPT_KEY)
        if not isinstance(receipt, dict):
            out.append((
                f"G4-receipt-missing:{tag}",
                f"[G4 运行收据缺失] {tag} active+standalone 但 evidence.{RECEIPT_KEY} 不是结构化对象",
            ))
            continue

        run_id = receipt.get("run_id")
        entry_hash = receipt.get("entry_hash")
        ng_hash = receipt.get("nine_gate_sha256")
        binding = receipt.get("binding_sha256")
        malformed = (
            receipt.get("schema") != 1
            or receipt.get("source") != "research_ledger"
            or not isinstance(run_id, str) or HEX_16.fullmatch(run_id) is None
            or not isinstance(entry_hash, str) or HEX_64.fullmatch(entry_hash) is None
            or not isinstance(ng_hash, str) or HEX_64.fullmatch(ng_hash) is None
            or not isinstance(binding, str) or HEX_64.fullmatch(binding) is None
        )
        if malformed:
            out.append((f"G4-receipt-malformed:{tag}", f"[G4 运行收据格式错误] {tag} 收据 schema/source/hash 身份不完整"))
            continue

        actual_ng_hash = _canonical_hash(row["nine_gate"])
        expected_binding = _receipt_binding(
            family=row["family"],
            version=str(row["version"]),
            run_id=run_id,
            entry_hash=entry_hash,
            nine_gate_sha256=ng_hash,
        )
        if ng_hash != actual_ng_hash or binding != expected_binding:
            out.append((
                f"G4-receipt-mismatch:{tag}",
                f"[G4 运行收据失配] {tag} 的 family/version 或 Nine-Gate 摘要与收据绑定不一致",
            ))
            continue

        if research_records is None:
            out.append((
                f"G4-ledger-unavailable:{tag}",
                f"[G4 运行账本不可用] {tag} 的自绑定收据无法对外部 hash-chain 记录验真",
            ))
            continue
        record = record_index.get((run_id, entry_hash))
        if record is None:
            out.append((f"G4-run-missing:{tag}", f"[G4 运行记录不存在] {tag} 收据未命中 research ledger 的 run_id+entry_hash"))
            continue
        record_ok = (
            record.get("source") == "nine_gate"
            and record.get("script") == NINE_GATE_SCRIPT
            and record.get("hypothesis") == tag
            and _record_run_id(record) == run_id
            and _record_entry_hash(record) == entry_hash
            and _canonical_hash(record.get("metrics") or {}) == ng_hash
        )
        if not record_ok:
            out.append((
                f"G4-run-mismatch:{tag}",
                f"[G4 运行记录失配] {tag} 的外部运行记录身份、内容哈希或 Nine-Gate metrics 不一致",
            ))
    return out


def find_diversifier_receipt_gaps(
    rows: list[dict], research_records: list[dict] | None = None
) -> list[tuple[str, str]]:
    """G5:active diversifier 必须有与机械字段绑定的 marginal_receipt。

    自洽校验与 register() 同源（verify_marginal_receipt_self_consistent）。
    若提供 research_records，则进一步要求 run_id+entry_hash 命中账本。
    """
    out: list[tuple[str, str]] = []
    record_index: dict[tuple[str, str], dict] = {}
    if research_records is not None:
        chain_problems = research_chain_problems(research_records)
        if chain_problems:
            return [
                (f"G5-ledger-chain:{index}", f"[G5 运行账本断链] {problem}")
                for index, problem in enumerate(chain_problems, 1)
            ]
        record_index = {
            (str(rec.get("run_id", "")), str(rec.get("entry_hash", ""))): rec
            for rec in research_records
            if rec.get("record_type") == "research_run"
        }

    for row in rows:
        if row["status"] not in ACTIVE_STATUS or row["track"] != "diversifier":
            continue
        tag = f"{row['family']}/{row['version']}"
        adm = row.get("admission") or {}
        if not isinstance(adm, dict):
            adm = {}
        # Prefer admission-embedded receipt; fall back to evidence for forward-compat.
        receipt = adm.get(MARGINAL_RECEIPT_KEY)
        if not isinstance(receipt, dict):
            receipt = (row.get("evidence") or {}).get(MARGINAL_RECEIPT_KEY)

        self_errors = verify_marginal_receipt_self_consistent(
            row["family"], str(row["version"]), adm, receipt if isinstance(receipt, dict) else None,
        )
        if self_errors:
            kind = "missing" if receipt is None or not isinstance(receipt, dict) else "mismatch"
            out.append((
                f"G5-receipt-{kind}:{tag}",
                f"[G5 diversifier 收据] {tag}: " + "; ".join(self_errors),
            ))
            continue

        if research_records is None:
            out.append((
                f"G5-ledger-unavailable:{tag}",
                f"[G5 运行账本不可用] {tag} 的自绑定 marginal 收据无法对外部 hash-chain 验真",
            ))
            continue

        run_id = receipt.get("run_id")
        entry_hash = receipt.get("entry_hash")
        record = record_index.get((str(run_id), str(entry_hash)))
        if record is None:
            out.append((
                f"G5-run-missing:{tag}",
                f"[G5 运行记录不存在] {tag} marginal 收据未命中 research ledger 的 run_id+entry_hash",
            ))
            continue
        # External record must carry the same marginal metrics payload hash.
        metrics = record.get("metrics") or {}
        expected_hash = receipt.get("marginal_sha256")
        actual_hash = _canonical_hash(marginal_metrics_payload(metrics))
        # Also accept metrics nested under metrics.marginal
        if actual_hash != expected_hash and isinstance(metrics.get("marginal"), dict):
            actual_hash = _canonical_hash(marginal_metrics_payload(metrics["marginal"]))
        if actual_hash != expected_hash:
            out.append((
                f"G5-run-mismatch:{tag}",
                f"[G5 运行记录失配] {tag} 外部记录 metrics 与 marginal_sha256 不一致",
            ))
            continue
        # Binding identity must match family/version in the receipt.
        expected_binding = _marginal_receipt_binding(
            family=row["family"],
            version=str(row["version"]),
            run_id=str(run_id),
            entry_hash=str(entry_hash),
            marginal_sha256=str(expected_hash),
        )
        if receipt.get("binding_sha256") != expected_binding:
            out.append((
                f"G5-receipt-mismatch:{tag}",
                f"[G5 收据绑定失配] {tag} family/version 与 binding 不一致",
            ))
    return out


def find_standalone_evidence_gaps(rows: list[dict]) -> list[tuple[str, str]]:
    """active standalone 的证据缺失 / 跳门却标通过 / DSR 不显著。返回 [(key, msg)]。

    G2 证据完整性：nine_gate 与 evidence 皆空 = 绕过准入；passed_all=true 却跳必算门 = 造假。
    G3 DSR 显著性：dsr_p 缺失(None)或 >=DSR_ALPHA = 多重测试惩罚下不显著的 standalone 在册
       (源 R-OBJECTIVE-001；与 strategy_registry.register() 的 DSR 门同口径，防降级后回流)。
    """
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
        dsr_p = ng.get("dsr_p")
        if dsr_p is None:
            out.append((f"G3-dsr-none:{tag}",
                        f"[G3 DSR未实算] {tag} active+standalone 但 nine_gate.dsr_p 缺失(None) — "
                        f"standalone 须有 DSR 多重测试惩罚证据，降 diversifier 或 status='候选'"))
        elif dsr_p >= DSR_ALPHA:
            out.append((f"G3-dsr-fail:{tag}",
                        f"[G3 DSR不显著] {tag} active+standalone 但 dsr_p={dsr_p:.4f}>={DSR_ALPHA} — "
                        f"多重测试惩罚下不显著，须降级"))
    return out


def check(ledger: dict | None = None, research_records: list[dict] | None = None) -> int:
    if ledger is None:
        ledger = json.loads(LEDGER.read_text())
        if research_records is None:
            try:
                research_records = _load_research_records()
            except ValueError as exc:
                print(f"台账证据完整性检查失败:{exc}")
                return 1
    rows = extract_versions(ledger)
    all_v = (
        find_cross_family_ic_copies(rows)
        + find_standalone_evidence_gaps(rows)
        + find_nine_gate_receipt_gaps(rows, research_records=research_records)
        + find_diversifier_receipt_gaps(rows, research_records=research_records)
    )
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
