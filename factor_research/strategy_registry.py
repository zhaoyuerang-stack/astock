"""
策略版本登记 —— 两层结构：母策略(family) → 版本(version)

核心理念：具体策略默认会失效，真正要管理的是「母策略生命周期」。
  · 母策略(family)：一个独立 alpha 家族，记 核心假设 / 适用市场 / 失效信号 / status
  · 版本(version)：该家族下的参数与数据口径变体，记 配置 / 绩效 / status / 备注
  · 数据口径(data_full/data_lake) 是版本属性，不再占版本号语义（防"喂出来的高收益"被当真）

版本 status 约定：候选 / 在册 / 退役 / 参考
母策略 status 约定：active / paused / retired

用法：
  python3 strategy_registry.py                      # 打印母策略分组对比表
  from strategy_registry import register_family, register
  register_family("momentum", "截面动量", hypothesis=..., regime=..., decay_signal=...)
  register("momentum", "v1.0", desc, config, data_scope, metrics, status="候选", notes=...)
"""
import argparse
import json
import os
import re
from pathlib import Path
from datetime import date

from engine.metrics import compute_hit

REGISTRY = Path(__file__).parent / "strategy_versions.json"

# 双轨准入：唯一允许长期占用「在册」的两条轨。
#   standalone  —— 单体达标（hit=True：年化>15% 且 回撤<20%）+ DSR 多重测试惩罚下显著（dsr_p<DSR_ALPHA）
#   diversifier —— 单体不达标但作为组合分流器（负相关 / 对组合夏普有正增量），须 rationale 佐证
# DSR 仅卡 standalone：diversifier 凭组合边际而非单体统计显著性入册，不受此门约束。
ADMISSION_TRACKS = ("standalone", "diversifier")

# standalone 准入的 DSR（Deflated Sharpe Ratio）多重测试惩罚显著性阈值。
# 来源 R-OBJECTIVE-001 / 9-Gate G8：单体达标(hit)不等于经得起搜索惩罚，dsr_p>=此值即多重测试下不显著。
DSR_ALPHA = 0.05

# 设计上即为「对冲分流器」的母策略：单体低收益 + 与主力负相关，靠组合层增量入册（diversifier 轨）。
# 仅这两族的对冲假设里显式写了「等额做空…对冲 Beta」并实测负相关，故迁移时自动归类为 diversifier。
DIVERSIFIER_FAMILIES = {"large-cap-growth-hedged", "hq-momentum-hedged"}


def _load():
    if not REGISTRY.exists():
        return {"families": []}
    data = json.loads(REGISTRY.read_text())
    if isinstance(data, list):
        # 旧扁平格式禁止静默视为空:返回空 dict 后任何 attach_*/register 触发 _save
        # 会把整本台账清空覆盖(退役纪律 R-7.4:不得删历史)。必须人工迁移。
        raise ValueError(
            f"{REGISTRY} 是旧扁平 list 格式,拒绝加载(防 _save 静默清空台账);"
            f"请先人工迁移为 {{'families': [...]}} 结构。")
    return data


def _version_key(version: str):
    """版本自然序:'v1.10' > 'v1.2'(字符串序会排反)。数字段转 int 比较,非数字兜底字符串。"""
    parts = re.split(r"(\d+)", str(version))
    return tuple(int(p) if p.isdigit() else p for p in parts)


def _save(data):
    data["families"].sort(key=lambda f: f["id"])
    # 原子写:临时文件 + os.replace,进程中途挂掉不会留下半截 JSON 损坏台账
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = REGISTRY.with_suffix(f".json.tmp.{os.getpid()}")
    tmp.write_text(payload)
    os.replace(tmp, REGISTRY)


def register_family(id, name, hypothesis="", regime="", decay_signal="", status="active",
                    style_betas=None, capacity_m=0.0, failure_boundaries=None):
    """登记/更新一个母策略（同 id 覆盖元信息，保留其下版本）"""
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == id), None)
    if fam is None:
        fam = {"id": id, "versions": []}
        data["families"].append(fam)
    
    update_dict = {
        "name": name,
        "hypothesis": hypothesis,
        "regime": regime,
        "decay_signal": decay_signal,
        "status": status,
        "style_betas": style_betas or {},
        "capacity_m": float(capacity_m),
        "failure_boundaries": failure_boundaries or {}
    }
    fam.update(update_dict)
    _save(data)
    return id


def register(family, version, desc, config, data_scope, metrics, status="候选", notes="",
             evidence=None, admission=None, nine_gate=None, date_str=None,
             spec=None, spec_hash=None):
    """登记/更新某母策略下的一个版本（同 family+version 覆盖）

    hit：一律由 ``engine.metrics.compute_hit`` 按 metrics 里的 annual/maxdd 重算并覆盖，
         禁止调用方手填——这是「修代码不修记分牌」铁律的机械执行点。
    admission：双轨准入声明 {"track": "standalone"|"diversifier", "rationale": str, ...}。
         status="在册" 必须通过准入：standalone 轨要求 hit=True；diversifier 轨要求 rationale。
         单体达标(hit=True)且未显式声明 → 自动补 standalone 轨（向后兼容）。
    nine_gate：Nine-Gate R2P 审计摘要 {dsr_p, psr, n_trials, pbo, wf_sharpe, cv_sharpe, ...}。
    evidence：证据链锚点 {"hypothesis_id": str, "experiment_ids": [str,...]}（默认空 dict）。
    date_str：保留/指定登记日期；缺省时同号覆盖保留原日期，新增则取今日。
    """
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == family), None)
    if fam is None:
        raise ValueError(f"母策略 '{family}' 未登记，请先 register_family('{family}', ...)")

    # 0) ExecutableStrategySpec 校验(Task 5)：提供 spec 则身份必须自洽——
    #    spec_hash 与重算一致、family/version 与登记参数一致。不提供则向后兼容(历史/手动登记)。
    spec_record = None
    if spec is not None:
        from core.strategy_spec import ExecutableStrategySpec
        parsed = ExecutableStrategySpec.from_dict(spec)
        parsed.validate()
        if spec_hash is not None and parsed.spec_hash != spec_hash:
            raise ValueError(
                f"{family}/{version} spec_hash 不匹配：重算={parsed.spec_hash[:12]} 传入={str(spec_hash)[:12]}")
        if parsed.family != family or parsed.version != version:
            raise ValueError(
                f"策略身份不匹配：spec={parsed.family}/{parsed.version} 登记={family}/{version}")
        spec_record = {"spec": parsed.to_dict(), "spec_hash": parsed.spec_hash}

    # 1) hit 由公式重算覆盖——杜绝手填记分牌
    metrics = dict(metrics or {})
    a, dd = metrics.get("annual"), metrics.get("maxdd")
    if a is not None and dd is not None:
        metrics["hit"] = compute_hit(a, dd)
    hit = bool(metrics.get("hit", False))

    # 2) 「在册」必须通过双轨准入
    adm = dict(admission or {})
    if status == "在册":
        track = adm.get("track")
        if track is None and hit:
            adm = {"track": "standalone", "rationale": "单体达标（年化>15% 且 回撤<20%）"}
        elif track is None and not hit:
            raise ValueError(
                f"{family}/{version} 不能登记为「在册」：单体不达标"
                f"（hit=False，年化={a}，回撤={dd}），且未声明 diversifier 准入。"
                f"请传 admission={{'track':'diversifier','rationale':...}} 或降级 status。")
        elif track == "standalone" and not hit:
            raise ValueError(
                f"{family}/{version} standalone 准入要求 hit=True，但单体不达标（年化={a}，回撤={dd}）。")
        elif track == "diversifier" and not (adm.get("rationale") or "").strip():
            raise ValueError(
                f"{family}/{version} diversifier 准入要求 rationale（负相关 / 组合夏普增量依据）。")
        elif track not in ADMISSION_TRACKS:
            raise ValueError(
                f"{family}/{version} 未知 admission.track={track!r}（应为 {ADMISSION_TRACKS}）。")

        # standalone 轨：hit 之外，必须通过 DSR 多重测试惩罚（R-OBJECTIVE-001 / G8）。
        # 覆盖「显式声明 standalone」与上面「hit=True 自动补 standalone」两条路径。
        if adm.get("track") == "standalone":
            dsr_p = (nine_gate or {}).get("dsr_p")
            if dsr_p is None:
                raise ValueError(
                    f"{family}/{version} standalone 准入必须有 nine_gate.dsr_p——"
                    f"请先跑 9-Gate 审计（workflow/promote.py 或 run_nine_gates_all.py）。"
                    f"若靠组合边际入册，请改 admission={{'track':'diversifier','rationale':...}}；"
                    f"否则降 status='候选'。")
            if dsr_p >= DSR_ALPHA:
                raise ValueError(
                    f"{family}/{version} standalone 准入要求 DSR p<{DSR_ALPHA}，"
                    f"当前 dsr_p={dsr_p:.4f}——多重测试惩罚下不显著（hit 达标≠搜索后显著）。"
                    f"可改 diversifier 轨（需 rationale）或降 status='候选'/'参考'。")

    existing = next((v for v in fam["versions"] if v["version"] == version), None)
    reg_date = date_str or (existing.get("date") if existing else None) or str(date.today())
    fam["versions"] = [v for v in fam["versions"] if v["version"] != version]   # 同号覆盖
    fam["versions"].append({
        "version": version, "date": reg_date, "desc": desc,
        "config": config, "data_scope": data_scope, "metrics": metrics,
        "status": status, "notes": notes,
        "evidence": evidence or {},
        "admission": adm,
        "nine_gate": nine_gate or {},
        **({"executable_spec": spec_record} if spec_record else {}),
    })
    fam["versions"].sort(key=lambda v: _version_key(v["version"]))
    _save(data)
    return f"{family}/{version}"


def migrate_two_track_admission(apply: bool = True):
    """一次性迁移：用 compute_hit 重算全台账 hit，并按双轨准入规则裁定「在册」去留。

    规则（与 register() 闸门一致）：
      · 在册 且 hit=True            → 保留在册，admission=standalone
      · 在册 且 hit=False 且 对冲族   → 保留在册，admission=diversifier（rationale 取自 notes）
      · 在册 且 hit=False 且 非对冲族 → 降级（autoresearch_*/fundamental-momentum → 候选；其余 → 参考）
      · 非在册                       → 仅刷新 hit 与占位字段，不动 status

    幂等：再次运行不产生新变更。返回逐版本 transition 列表（供 CLI 打印 / 审计）。
    本函数在 registry 模块内，经 _save 走唯一写入口，未绕过台账写入纪律。
    """
    data = _load()
    transitions = []
    for fam in data["families"]:
        fid = fam["id"]
        for v in fam["versions"]:
            m = dict(v.get("metrics") or {})
            a, dd = m.get("annual"), m.get("maxdd")
            old_hit = m.get("hit")
            new_hit = compute_hit(a, dd) if (a is not None and dd is not None) else bool(old_hit)
            if a is not None and dd is not None:
                m["hit"] = new_hit
            v["metrics"] = m
            v["evidence"] = v.get("evidence") or {}
            v["nine_gate"] = v.get("nine_gate") or {}

            old_status = v.get("status")
            new_status, track = old_status, (v.get("admission") or {}).get("track", "—")

            if old_status == "在册":
                if new_hit:
                    v["admission"] = {"track": "standalone",
                                      "rationale": "单体达标（年化>15% 且 回撤<20%）"}
                    new_status, track = "在册", "standalone"
                elif fid in DIVERSIFIER_FAMILIES:
                    rationale = (v.get("notes") or "").strip()[:200] or "对冲分流器：等额做空对冲 Beta，与主力负相关"
                    v["admission"] = {"track": "diversifier", "rationale": rationale,
                                      "note": "迁移自动归类：对冲母策略，单体低收益+负相关，靠组合层增量入册"}
                    new_status, track = "在册", "diversifier"
                else:
                    new_status = "候选" if (fid.startswith("autoresearch_") or fid == "fundamental-momentum") else "参考"
                    v["status"] = new_status
                    v["admission"] = {}
                    track = "—（降级）"
            else:
                v["admission"] = v.get("admission") or {}

            transitions.append({
                "id": f"{fid}/{v['version']}",
                "old_status": old_status, "new_status": new_status,
                "old_hit": old_hit, "new_hit": new_hit, "track": track,
                "annual": a, "maxdd": dd,
            })

    if apply:
        _save(data)
    return transitions


def demote_dsr_insignificant_standalone(threshold: float = DSR_ALPHA, apply: bool = True):
    """一次性治理迁移（ADR-020 / R-OBJECTIVE-001）：把 DSR 多重测试惩罚下不显著的
    「在册 standalone」降为「参考」，保留历史绩效/配置/nine_gate，仅移出有效 alpha 池。

    判定：status=='在册' 且 admission.track=='standalone' 且 (dsr_p is None 或 dsr_p>=threshold)。
      · status → '参考'，admission → {}（不再占用准入轨）
      · metrics / evidence / nine_gate 原样保留（R-7.4 退役纪律：不得删历史）
      · 写入 dsr_demotion 审计块，记降级前轨道 / dsr_p / 阈值 / 依据

    幂等：降级后 status 变「参考」，再次运行不再命中。经 _save 走台账唯一写入口。
    返回逐版本 transition 列表（供 CLI 打印 / 审计）。
    """
    data = _load()
    transitions = []
    for fam in data["families"]:
        fid = fam["id"]
        for v in fam["versions"]:
            adm = v.get("admission") or {}
            if v.get("status") != "在册" or adm.get("track") != "standalone":
                continue
            dsr_p = (v.get("nine_gate") or {}).get("dsr_p")
            if dsr_p is not None and dsr_p < threshold:
                continue  # DSR 达标，留任在册 standalone
            v["status"] = "参考"
            v["admission"] = {}
            v["dsr_demotion"] = {
                "from_status": "在册", "from_track": "standalone",
                "dsr_p": dsr_p, "threshold": threshold,
                "rule": "R-OBJECTIVE-001 / 9-Gate G8（DSR 多重测试惩罚下不显著）",
                "date": str(date.today()),
            }
            transitions.append({
                "id": f"{fid}/{v['version']}", "dsr_p": dsr_p,
                "new_status": "参考", "reason": "DSR 不显著（None 或 >=阈值）",
            })
    if apply:
        _save(data)
    return transitions


def attach_nine_gate(family, version, summary, evidence=None):
    """把一次 Nine-Gate 审计摘要（NineGatesReport.summarize()）写入指定版本的 nine_gate 字段。

    可选 evidence 同步绑定证据链 {"hypothesis_id":..., "experiment_ids":[...]}。
    经 _save 走台账唯一写入口；不改 status/metrics。
    """
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == family), None)
    if fam is None:
        raise ValueError(f"母策略 '{family}' 未登记")
    v = next((x for x in fam["versions"] if x["version"] == version), None)
    if v is None:
        raise ValueError(f"版本 '{family}/{version}' 不存在")
    v["nine_gate"] = dict(summary or {})
    if evidence:
        ev = dict(v.get("evidence") or {})
        ev.update(evidence)
        v["evidence"] = ev
    _save(data)
    return f"{family}/{version}"


def attach_data_incident(family, version, incident):
    """Append a data incident to version evidence without changing lifecycle status."""
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == family), None)
    if fam is None:
        raise ValueError(f"母策略 '{family}' 未登记")
    item = next((v for v in fam["versions"] if v["version"] == version), None)
    if item is None:
        raise ValueError(f"版本 '{family}/{version}' 不存在")
    evidence = dict(item.get("evidence") or {})
    incidents = list(evidence.get("data_incidents") or [])
    incident = dict(incident or {})
    incident_id = incident.get("incident_id")
    incidents = [
        existing for existing in incidents
        if not incident_id or existing.get("incident_id") != incident_id
    ]
    incidents.append(incident)
    evidence["data_incidents"] = incidents
    evidence["production_blocked"] = any(not row.get("resolved") for row in incidents)
    item["evidence"] = evidence
    _save(data)
    return f"{family}/{version}"


def attach_decay_check(family, version, result, *, checked_at=None):
    """把一次 governance/decay.py::decay_check() 的结果写入指定版本的 decay_check 字段。

    版本级(不是家族级):decay_check 按 run_active() 的每条腿算,与既有家族级静态
    decay_signal(注册时写的失效条件文字)是两件事,不互相覆盖。只读监控信号,
    不改 status/admission——是否退役仍走 retire_version() 人工/workflow 决策。
    经 _save 走台账唯一写入口。
    """
    from datetime import datetime, timezone
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == family), None)
    if fam is None:
        raise ValueError(f"母策略 '{family}' 未登记")
    v = next((x for x in fam["versions"] if x["version"] == version), None)
    if v is None:
        raise ValueError(f"版本 '{family}/{version}' 不存在")
    v["decay_check"] = {
        **dict(result or {}),
        "checked_at": checked_at or datetime.now(timezone.utc).isoformat(),
    }
    _save(data)
    return f"{family}/{version}"


def attach_catalog_status(family, version, status, *, marginal=None, changed_at=None):
    """把一次边际贡献定级(governance/marginal.py::marginal_alpha 的残差法判决)写入
    指定版本的 catalog_status 字段。

    portfolio/strategy_runners.py::RESEARCH_STRATEGY_CATALOG 模块加载时读这个字段
    覆盖写死的 status,取代过去"算完只打印,人工去改代码里的字符串"的流程
    (workflow/promote.py::_run_marginal 调用本函数)。

    status 只表示"是否并入组合权重计算"(ACTIVE/SHADOW),不是准入闸——不改
    version 的 status/admission(那是 strategy_registry.register() 的事)。
    经 _save 走台账唯一写入口。
    """
    from datetime import datetime, timezone
    if status not in {"ACTIVE", "SHADOW"}:
        raise ValueError(f"catalog_status 只能是 ACTIVE/SHADOW,收到 {status!r}")
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == family), None)
    if fam is None:
        raise ValueError(f"母策略 '{family}' 未登记")
    v = next((x for x in fam["versions"] if x["version"] == version), None)
    if v is None:
        raise ValueError(f"版本 '{family}/{version}' 不存在")
    v["catalog_status"] = {
        "status": status,
        "marginal": dict(marginal or {}),
        "changed_at": changed_at or datetime.now(timezone.utc).isoformat(),
    }
    _save(data)
    return f"{family}/{version}"


def attach_executable_spec(
    family,
    version,
    spec,
    spec_hash,
    *,
    require_revalidation=True,
):
    """Attach a validated executable identity without copying old evidence to it."""
    from core.strategy_spec import ExecutableStrategySpec

    parsed = ExecutableStrategySpec.from_dict(spec)
    parsed.validate()
    if parsed.family != family or parsed.version != version:
        raise ValueError("strategy identity mismatch")
    if parsed.spec_hash != spec_hash:
        raise ValueError("strategy spec hash mismatch")
    data = _load()
    fam = next((f for f in data["families"] if f["id"] == family), None)
    if fam is None:
        raise ValueError(f"母策略 '{family}' 未登记")
    item = next((v for v in fam["versions"] if v["version"] == version), None)
    if item is None:
        raise ValueError(f"版本 '{family}/{version}' 不存在")
    item["executable_spec"] = {"spec": parsed.to_dict(), "spec_hash": parsed.spec_hash}
    evidence = dict(item.get("evidence") or {})
    evidence["spec_migration"] = {
        "spec_hash": parsed.spec_hash,
        "requires_revalidation": bool(require_revalidation),
    }
    if require_revalidation:
        evidence["production_blocked"] = True
    item["evidence"] = evidence
    _save(data)
    return f"{family}/{version}"


def retire_version(family, version, *, reason, evidence_refs=(), actor="workflow",
                   control_event_path=None):
    """唯一的版本退役通道(ADR-017 处置 + Task 15 状态机接线)。

    经状态机校验合法转换(非 REGISTERED/DEPLOYED/SUSPENDED 源状态拒绝,不落盘)、追加
    control_events 链式审计、把退役原因与证据指针写入 evidence.retirement(不删除历史字段)。
    """
    import uuid
    from datetime import datetime, timezone

    from governance.control_events import append_event, DEFAULT_LOG as CE_DEFAULT_LOG
    from governance.state_machine import CN_TO_STATE

    data = _load()
    fam = next((f for f in data["families"] if f["id"] == family), None)
    if fam is None:
        raise ValueError(f"母策略 '{family}' 未登记")
    item = next((v for v in fam["versions"] if v["version"] == version), None)
    if item is None:
        raise ValueError(f"版本 '{family}/{version}' 不存在")

    from_state = CN_TO_STATE.get(item.get("status"), item.get("status"))
    spec_hash = ((item.get("executable_spec") or {}).get("spec_hash")) or ""

    append_event(
        event_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc).isoformat(),
        actor=actor, family=family, version=version, spec_hash=spec_hash,
        from_state=from_state, to_state="RETIRED", reason_code=reason,
        evidence_refs=tuple(evidence_refs),
        path=control_event_path or CE_DEFAULT_LOG,
    )  # 非法转换在此抛 IllegalTransition,不落盘注册表

    evidence = dict(item.get("evidence") or {})
    evidence["retirement"] = {
        "reason": reason,
        "evidence_refs": list(evidence_refs),
        "retired_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
    }
    item["evidence"] = evidence
    item["status"] = "退役"
    _save(data)
    return f"{family}/{version}"


def show():
    """按母策略分组打印台账"""
    data = _load()
    if not data["families"]:
        print("暂无登记母策略"); return
    for fam in data["families"]:
        print(f"\n■ 母策略 {fam['id']}（{fam.get('name','')}）  status={fam.get('status','')}")
        for k, label in (("hypothesis", "假设"), ("regime", "适用"), ("decay_signal", "失效信号")):
            if fam.get(k):
                print(f"    {label}：{fam[k]}")
        
        # New fields formatting
        if fam.get("style_betas"):
            betas_str = ", ".join(f"{k}: {v:+.2f}" for k, v in fam["style_betas"].items())
            print(f"    风格暴露：{betas_str}")
        if fam.get("capacity_m", 0.0) > 0.0:
            print(f"    估计容量：{fam['capacity_m']:.1f} M (百万 CNY)")
        if fam.get("failure_boundaries"):
            bounds_str = ", ".join(f"{k}: {v}" for k, v in fam["failure_boundaries"].items())
            print(f"    失效边界：{bounds_str}")

        print(f"  {'版本':<6}{'数据口径':<26}{'年化':>8}{'回撤':>8}{'夏普':>6}{'达标':>5}{'状态':>6}  备注")
        print("  " + "-" * 100)
        for v in fam["versions"]:
            m, ds = v.get("metrics", {}), v.get("data_scope", {})
            if isinstance(ds, str):
                scope = ds
            else:
                source = ds.get("source", "unknown")
                period = ds.get("period", "unknown")
                scope = f"{source}·{period}{'·幸存者偏差' if ds.get('survivorship_bias') else ''}"
            print(f"  {v['version']:<6}{scope:<26}{m.get('annual', 0.0):>7.1%}{m.get('maxdd', 0.0):>8.1%}"
                  f"{m.get('sharpe', 0.0):>6.2f}{'✅' if m.get('hit') else '❌':>5}{v.get('status',''):>6}  {v.get('notes','')}")
            ev = v.get("evidence") or {}
            if ev.get("hypothesis_id"):
                print(f"  {'':<6}↳ 证据：hyp={ev['hypothesis_id'][:8]} / {len(ev.get('experiment_ids', []))} 实验")
            adm = v.get("admission") or {}
            if v.get("status") == "在册" and adm.get("track"):
                print(f"  {'':<6}↳ 准入：{adm['track']}")
            ng = v.get("nine_gate") or {}
            if ng:
                print(f"  {'':<6}↳ Nine-Gate：DSR_p={ng.get('dsr_p','?')} PSR={ng.get('psr','?')} "
                      f"PBO={ng.get('pbo','?')} WF_sharpe={ng.get('wf_sharpe','?')}")


# ── 命令行入口 ──
if __name__ == "__main__":
    import os; os.chdir(Path(__file__).parent)

    ap = argparse.ArgumentParser()
    ap.add_argument("--migrate", action="store_true",
                    help="重算全台账 hit + 双轨准入裁定（apply）")
    ap.add_argument("--dry-run", action="store_true", help="配合 --migrate：只预览不落盘")
    args = ap.parse_args()

    if args.migrate:
        trans = migrate_two_track_admission(apply=not args.dry_run)
        changed = [t for t in trans if t["new_status"] != t["old_status"] or bool(t["new_hit"]) != bool(t["old_hit"])]
        mode = "DRY-RUN（未落盘）" if args.dry_run else "已落盘"
        print(f"双轨准入迁移 {mode}：{len(trans)} 版本，其中 {len(changed)} 个状态/hit 变更\n")
        print(f"  {'版本':<38}{'旧状态':>6}{'→新状态':>9}{'旧hit':>7}{'→新hit':>7}  轨")
        print("  " + "-" * 92)
        for t in trans:
            mark = " *" if (t in changed) else "  "
            print(f"{mark}{t['id']:<38}{str(t['old_status']):>6}{str(t['new_status']):>9}"
                  f"{str(t['old_hit']):>7}{str(t['new_hit']):>7}  {t['track']}")
        print()
        show()
    else:
        print("当前母策略台账：\n")
        show()
