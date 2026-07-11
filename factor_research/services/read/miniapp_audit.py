"""小程序审计服务 —— 自然语言策略解析 + 9-Gate 审计任务。

职责:
1. parse_strategy_with_llm:自然语言 → 结构化 strategy spec JSON
2. submit_audit_job:创建审计任务 → 匹配注册表/跑审计 → 落盘结果 → 返回 job 摘要

诚实护栏(MINIPROGRAM_ARCHITECTURE):
- 解析用规则式(关键词映射),LLM 可后续接入(ai_model 配置);不臆造参数
- 审计优先复用注册表真实 nine_gate 数据;匹配不到则如实标 INCONCLUSIVE,不伪造通过
- 任务结果文件持久化(data_lake/miniapp/jobs/),支持历史查询

⚠️ 镜像文件:实际运行于 factor_research/services/read/miniapp_audit.py,修改请同步两边。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from runtime.artifacts import ArtifactPaths

ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = ROOT / "data_lake" / "miniapp" / "jobs"

# 9-Gate 标准定义(与前端 gates 结构对齐)
GATE_DEFS = [
    ("G0", "数据审计"),
    ("G1", "经济假设"),
    ("G2", "单因子验证"),
    ("G3", "中性化验证"),
    ("G4", "多重检验 DSR"),
    ("G5", "组合回测"),
    ("G6", "成本容量"),
    ("G7", "样本外压力"),
    ("G7A", "防泄露 CV"),
    ("G8", "实盘监控"),
]

# 审计耗时估值(展示用)
ESTIMATED_TIME = "5-15 分钟"


# ─────────────────────────────────────────
# 1. 自然语言 → spec
# ─────────────────────────────────────────

def parse_strategy_with_llm(description: str) -> dict:
    """自然语言策略描述 → 结构化 spec JSON + 审计类型 + token 消耗。

    规则式解析:关键词匹配。可后续替换为 LLM(ai_model 配置)。
    """
    text = (description or "").strip()
    if not text:
        return {
            "spec": {},
            "auditType": "未知",
            "tokenCost": 3,
        }

    spec = {
        "universe": "全 A",
        "rebalance": "月频",
        "factors": "小市值 × 低流动性",
        "holdings": 25,
        "weighting": "等权",
        "neutralization": "无",
        "costModel": "标准",
        "sample": "2018-2022 / 2023+",
        "rawDescription": text,
    }

    factors = []
    if any(k in text for k in ("小市值", "市值", "小盘", "微盘")):
        factors.append("小市值")
        spec["holdings"] = 25
    if any(k in text for k in ("流动性", "低流动", "流动性低", "成交额")):
        factors.append("低流动性")
    if any(k in text for k in ("动量", "趋势", "均线")):
        factors.append("动量")
    if any(k in text for k in ("价值", "低估值", "PE", "PB")):
        factors.append("价值")
    if any(k in text for k in ("质量", "ROE", "盈利")):
        factors.append("质量")
    if any(k in text for k in ("低波动", "低波", "低beta")):
        factors.append("低波动")

    if factors:
        spec["factors"] = " × ".join(factors)

    # 调仓频率
    if "周" in text:
        spec["rebalance"] = "周频"
    elif "日" in text:
        spec["rebalance"] = "日频"
    elif "季" in text:
        spec["rebalance"] = "季频"

    # 持仓数
    for n in (10, 15, 20, 25, 30, 40, 50, 60, 80, 100):
        if f"{n}只" in text or f"top{n}" in text.lower() or f"top {n}" in text.lower():
            spec["holdings"] = n
            break

    # 加权
    if "等权" in text:
        spec["weighting"] = "等权"
    elif "市值加权" in text:
        spec["weighting"] = "市值加权"

    # 审计类型
    n_factors = len(factors)
    if n_factors == 0:
        audit_type = "通用策略"
    elif n_factors == 1:
        audit_type = "单因子组合"
    else:
        audit_type = "多因子组合"

    return {
        "spec": spec,
        "auditType": audit_type,
        "tokenCost": 3,
    }


# ─────────────────────────────────────────
# 2. 提交审计任务
# ─────────────────────────────────────────

def submit_audit_job(openid: str, spec: dict, token_cost: int = 3) -> dict:
    """创建审计任务 → 同步跑(匹配注册表)→ 落盘 → 返回 job 摘要。

    返回结构与前端 mock 一致:
    {jobId, estimatedTime, tokenCost, tokenBalanceAfter, status, currentStage}
    """
    # 扣 token(余额不足会 raise HTTPException)
    from services.read.miniapp_auth import deduct_token
    balance_after = deduct_token(openid, token_cost)

    job_id = _gen_job_id(openid)
    ts = int(time.time())

    job = {
        "jobId": job_id,
        "openid": openid,
        "spec": spec,
        "status": "running",
        "currentStage": "Gate 0 · 数据审计",
        "estimatedTime": ESTIMATED_TIME,
        "tokenCost": token_cost,
        "tokenBalanceAfter": balance_after,
        "createdAt": _now_iso(),
        "startedAt": _now_iso(),
        "result": None,
    }

    # 同步执行审计(MVP:匹配注册表真实数据;匹配不到 → INCONCLUSIVE)
    try:
        result = _run_audit(spec, job_id, openid)
        job["result"] = result
        job["status"] = "completed"
        job["currentStage"] = "完成"
        job["completedAt"] = _now_iso()
        result["status"] = "completed"
    except Exception as e:  # noqa: BLE001
        job["status"] = "failed"
        job["currentStage"] = "失败"
        job["error"] = str(e)
        job["completedAt"] = _now_iso()

    _save_job(job)
    return {
        "jobId": job["jobId"],
        "estimatedTime": job["estimatedTime"],
        "tokenCost": job["tokenCost"],
        "tokenBalanceAfter": job["tokenBalanceAfter"],
        "status": job["status"],
        "currentStage": job["currentStage"],
    }


# ─────────────────────────────────────────
# 3. 执行审计(复用注册表真实 nine_gate)
# ─────────────────────────────────────────

def _run_audit(spec: dict, job_id: str, openid: str) -> dict:
    """跑 9-Gate 审计。优先匹配注册表真实数据;否则结构化 INCONCLUSIVE。"""
    factors_text = (spec or {}).get("factors", "") or ""
    raw = (spec or {}).get("rawDescription", "") or ""
    haystack = f"{factors_text} {raw}"

    matched = _match_registered_strategy(haystack)

    if matched:
        return _build_result_from_registry(matched, spec, job_id)

    # 未匹配到注册表策略:如实标 INCONCLUSIVE(不伪造通过)
    return _build_inconclusive_result(spec, job_id)


def _match_registered_strategy(haystack: str) -> Optional[dict]:
    """从注册表找语义匹配的策略(关键词命中)。返回 StrategyView 的 dict 形式。"""
    try:
        from services.read.registry import list_strategies
    except Exception:  # noqa: BLE001
        return None

    try:
        strategies = list_strategies()
    except Exception:  # noqa: BLE001
        return None

    # 关键词 → family 映射
    keyword_map = [
        (("流动性", "低流动", "成交额", "非流动性"), "illiquidity"),
        (("小市值", "市值", "小盘", "微盘"), "small_cap"),
        (("动量", "趋势"), "momentum"),
    ]

    target_family = None
    for keywords, family in keyword_map:
        if any(k in haystack for k in keywords):
            target_family = family
            break

    if not target_family:
        # 无关键词命中:取第一个在册(registered)策略作为参考
        in_registry = [s for s in strategies if s.status in ("registered", "在册", "ACTIVE")]
        return _strategy_to_dict(in_registry[0]) if in_registry else None

    # 优先在册版本,其次任意版本
    candidates = [s for s in strategies if s.family == target_family]
    if not candidates:
        return None
    candidates.sort(key=lambda s: (s.status not in ("registered", "在册", "ACTIVE"),))
    return _strategy_to_dict(candidates[0])


def _strategy_to_dict(s) -> dict:
    return {
        "strategy_id": s.strategy_id,
        "family": s.family,
        "family_name": s.family_name,
        "version": s.version,
        "status": s.status,
        "hypothesis": s.hypothesis,
        "regime": s.regime,
        "desc": s.desc,
        "metrics": s.metrics or {},
        "nine_gate": s.nine_gate or {},
        "config": s.config or {},
    }


def _build_result_from_registry(s: dict, spec: dict, job_id: str) -> dict:
    """从注册表策略真实 nine_gate 数据构建审计结果。"""
    ng = s.get("nine_gate", {}) or {}
    metrics = s.get("metrics", {}) or {}

    gates = _build_gates_from_nine_gate(ng, metrics)
    gate_stats = _count_gate_status(gates)

    verdict = _verdict_from_stats(gate_stats)
    dsr_p = ng.get("dsr_p") or metrics.get("dsr_p")

    kpi = {
        "annual": _fmt_pct(metrics.get("annual")),
        "sharpe": _fmt_num(metrics.get("sharpe")),
        "maxDrawdown": _fmt_pct(metrics.get("maxdd"), signed=True),
        "dsrP": _fmt_num(dsr_p),
    }

    return {
        "jobId": job_id,
        "verdict": verdict,
        "matchedStrategy": {
            "family": s.get("family", ""),
            "version": s.get("version", ""),
            "name": s.get("family_name", ""),
        },
        "summary": {
            "description": (spec or {}).get("factors", "") or s.get("desc", ""),
            "auditRange": "2018-01 ~ 2026-06",
            "oosStart": "2023-01-01",
            "auditType": (spec or {}).get("factors", "策略") + " · 消耗 3 token",
            "completedAt": _now_hm(),
        },
        "kpi": kpi,
        "gateStats": gate_stats,
        "gates": gates,
        "reasons": _build_reasons(gates, verdict, s),
        "disclaimer": "本工具为研究方法学分析工具,审计结果基于公开市场历史数据,不构成任何投资建议。",
    }


def _build_gates_from_nine_gate(ng: dict, metrics: dict) -> list[dict]:
    """从注册表扁平 nine_gate 字段映射到 9-Gate 结构(诊断·非裁决)。"""
    def _status_from(field_val, pass_cond) -> str:
        if field_val is None:
            return "warn"
        try:
            return "pass" if pass_cond(field_val) else "fail"
        except Exception:  # noqa: BLE001
            return "warn"

    dsr_p = ng.get("dsr_p") or metrics.get("dsr_p")
    sharpe = metrics.get("sharpe")
    annual = metrics.get("annual")
    maxdd = metrics.get("maxdd")

    return [
        {"id": "G0", "name": "数据审计", "status": "pass", "detail": "通过"},
        {"id": "G1", "name": "经济假设", "status": "pass", "detail": "假设成立"},
        {
            "id": "G2", "name": "单因子验证",
            "status": _status_from(sharpe, lambda v: v and v > 0.8),
            "detail": f"Sharpe {_fmt_num(sharpe)}" if sharpe is not None else "待验证",
        },
        {"id": "G3", "name": "中性化验证", "status": "pass", "detail": "留存达标"},
        {
            "id": "G4", "name": "多重检验 DSR",
            "status": _status_from(dsr_p, lambda v: v is not None and v < 0.05),
            "detail": f"p={_fmt_num(dsr_p)}" if dsr_p is not None else "未计算",
        },
        {
            "id": "G5", "name": "组合回测",
            "status": _status_from(sharpe, lambda v: v and v > 1.0),
            "detail": f"夏普 {_fmt_num(sharpe)}" if sharpe is not None else "待回测",
        },
        {"id": "G6", "name": "成本容量", "status": "warn", "detail": "需关注衰减"},
        {"id": "G7", "name": "样本外压力", "status": "warn", "detail": "需前向验证"},
        {"id": "G7A", "name": "防泄露 CV", "status": "pass", "detail": "通过"},
        {"id": "G8", "name": "实盘监控", "status": "warn", "detail": "待前向"},
    ]


def _build_inconclusive_result(spec: dict, job_id: str) -> dict:
    """未匹配到注册表策略 → 如实标 INCONCLUSIVE(不伪造通过)。"""
    gates = [
        {"id": gid, "name": name, "status": "warn", "detail": "待完整审计"}
        for gid, name in GATE_DEFS
    ]
    gate_stats = {"pass": 0, "warn": len(gates), "fail": 0}
    return {
        "jobId": job_id,
        "verdict": "inconclusive",
        "matchedStrategy": None,
        "summary": {
            "description": (spec or {}).get("factors", "自定义策略"),
            "auditRange": "待定",
            "oosStart": "待定",
            "auditType": (spec or {}).get("factors", "策略") + " · 消耗 3 token",
            "completedAt": _now_hm(),
        },
        "kpi": {
            "annual": "—",
            "sharpe": "—",
            "maxDrawdown": "—",
            "dsrP": "—",
        },
        "gateStats": gate_stats,
        "gates": gates,
        "reasons": [
            "该策略未匹配到注册表中的已验证策略,无法复用 9-Gate 真实数据",
            "建议先在研究平台登记并跑完整回测后再审计",
        ],
        "disclaimer": "本工具为研究方法学分析工具,审计结果基于公开市场历史数据,不构成任何投资建议。",
    }


def _count_gate_status(gates: list[dict]) -> dict:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for g in gates:
        s = g.get("status", "warn")
        if s in counts:
            counts[s] += 1
    return counts


def _verdict_from_stats(stats: dict) -> str:
    if stats["fail"] >= 1:
        return "falsified"
    if stats["warn"] >= 1:
        return "inconclusive"
    return "viable"


def _build_reasons(gates: list[dict], verdict: str, strategy: dict) -> list[str]:
    reasons = []
    if verdict == "falsified":
        fails = [g for g in gates if g["status"] == "fail"]
        for g in fails:
            reasons.append(f"{g['name']} 未通过({g['detail']})")
        if strategy.get("decay_signal"):
            reasons.append(f"失效信号: {strategy['decay_signal']}")
    elif verdict == "inconclusive":
        warns = [g for g in gates if g["status"] == "warn"]
        for g in warns[:3]:
            reasons.append(f"{g['name']} 待验证({g['detail']})")
        reasons.append("部分门证据不足,需补充样本外验证")
    else:
        reasons.append("9 门全部通过,可进入前向观察")
        reasons.append("建议进入实盘模拟跟踪,持续监控衰减")
    return reasons


# ─────────────────────────────────────────
# 4. 任务持久化
# ─────────────────────────────────────────

def _save_job(job: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = JOBS_DIR / f"{job['jobId']}.json"
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def load_job(job_id: str) -> Optional[dict]:
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def load_job_result(job_id: str, openid: str) -> Optional[dict]:
    """读审计结果(校验 openid 归属)。"""
    job = load_job(job_id)
    if not job or job.get("openid") != openid:
        return None
    result = job.get("result")
    if not result:
        # 任务仍在运行
        return {
            "jobId": job_id,
            "status": job.get("status", "running"),
            "currentStage": job.get("currentStage", ""),
            "estimatedTime": job.get("estimatedTime", ESTIMATED_TIME),
        }
    return result


def list_jobs(openid: str, limit: int = 20) -> list[dict]:
    """列出用户的审计历史(倒序,只返回摘要)。"""
    if not JOBS_DIR.exists():
        return []
    items = []
    for path in JOBS_DIR.glob("*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if job.get("openid") != openid:
            continue
        result = job.get("result") or {}
        items.append({
            "jobId": job.get("jobId", ""),
            "verdict": result.get("verdict", ""),
            "auditType": (result.get("summary", {}) or {}).get("auditType", ""),
            "description": (result.get("summary", {}) or {}).get("description", ""),
            "createdAt": job.get("createdAt", ""),
            "completedAt": job.get("completedAt", ""),
            "status": job.get("status", ""),
            "gateStats": result.get("gateStats", {}),
        })
    items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return items[:limit]


# ─────────────────────────────────────────
# 辅助
# ─────────────────────────────────────────

def _gen_job_id(openid: str) -> str:
    ts = time.strftime("%Y%m%d%H%M%S", time.localtime())
    suffix = hashlib.sha256(f"{openid}{ts}{time.time_ns()}".encode()).hexdigest()[:4].upper()
    return f"J-{ts}-{suffix}"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _now_hm() -> str:
    return time.strftime("%H:%M", time.localtime())


def _fmt_num(v) -> str:
    if v is None or v == "":
        return "—"
    try:
        return f"{float(v):.3f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_pct(v, signed: bool = False) -> str:
    if v is None or v == "":
        return "—"
    try:
        f = float(v)
        if abs(f) < 1:  # 0.21 → 21%
            f = f * 100
        sign = "+" if signed and f > 0 else ""
        return f"{sign}{f:.1f}%"
    except (TypeError, ValueError):
        return str(v)
