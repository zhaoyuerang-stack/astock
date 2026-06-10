"""knowledge/graph.py — 机器可读知识图谱(空容器版)。

核心理念:
  pending_lessons 是"模式型"学习记录(timing_peek 发生过),不绑定候选身份、不 gate。
  知识图谱把每条验证结论绑定到候选身份(Hypothesis),并产出机器可读 SearchGate,
  让搜索引擎在花算力之前先跳过/降权已证伪的候选。

  每条 Finding 带:
    - 保质期 expires(到期自动重测,避免"已解决的问题成为探索的坟墓")
    - 父依赖 depends_on(父结论失效 → 级联重测)
    - SearchGate(机器可读搜索约束:SKIP / DEPRIORITIZE / REQUIRE_RETEST)

  与 alpha_engine 的差异(借机制不照搬结论):
    - 零预置结论;findings 全部由 record_from_validation() 现场生长
    - 默认 DEPRIORITIZE 而非 SKIP;仅 phase1 合成审计 FAIL(真坏候选)才 SKIP
    - 不施加边际律门槛(那条忽略相关性符号);边际真值归 line3_marginal
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

# 失败候选的默认动作:按 stage 分级。
# phase1 合成审计失败 = 候选真坏(leaky/未来函数)→ 永久 SKIP 同参数。
# 其余阶段(L0~L3 / phase2 / phase3)"alpha 弱" = regime/区间依赖 → DEPRIORITIZE + 保质期。
_HARD_FAIL_STAGES = {"phase1", "synthetic", "phase1_synthetic"}

_PRIORITY = {"SKIP": 0.0, "DEPRIORITIZE": 0.3, "REQUIRE_RETEST": 1.0}


# ── 候选身份提取(duck-typed Hypothesis)────────────────────────────────────

def _atom_attrs(hyp) -> dict:
    """从 Hypothesis 抽出可匹配属性(字符串化,便于稳定比较)。"""
    attrs = {
        "factor_fn_name": getattr(hyp, "factor_fn_name", ""),
        "timing_fn_name": getattr(hyp, "timing_fn_name", "") or "",
    }
    for k, v in (getattr(hyp, "factor_params", {}) or {}).items():
        attrs[str(k)] = str(v)
    return attrs


# ── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SearchGate:
    """机器可读的搜索空间约束。"""
    match: dict                 # {"factor_fn_name": "...", "window": "60"} —— 子集匹配
    action: str                 # "SKIP" / "DEPRIORITIZE" / "REQUIRE_RETEST"
    reason: str = ""

    def matches(self, hyp) -> bool:
        attrs = _atom_attrs(hyp)
        for k, v in self.match.items():
            if str(attrs.get(k)) != str(v):
                return False
        return True


@dataclass
class Finding:
    """一条带保质期的研究结论。"""
    id: str
    statement: str
    domain: str = "factor"
    confidence: float = 0.8
    evidence: list = field(default_factory=list)
    created: str = ""
    expires: str = ""           # ISO date;空 = 永不过期
    depends_on: list = field(default_factory=list)
    gates: list = field(default_factory=list)   # list[SearchGate]
    metrics: dict = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if not self.expires:
            return False
        return date.today().isoformat() > self.expires

    @property
    def is_valid(self) -> bool:
        return not self.is_expired


# ── 知识图谱 ────────────────────────────────────────────────────────────────

class KnowledgeGraph:
    """研究结论的有向图(节点=Finding,边=depends_on)。"""

    def __init__(self, store_path: Optional[str] = None):
        self._findings: dict[str, Finding] = {}
        self.store_path = store_path
        if store_path and os.path.exists(store_path):
            self.load(store_path)

    # ── 增查 ──
    def add(self, finding: Finding) -> None:
        self._findings[finding.id] = finding
        if self.store_path:
            self.save(self.store_path)

    def get(self, finding_id: str) -> Optional[Finding]:
        return self._findings.get(finding_id)

    def all_valid(self) -> list:
        return [f for f in self._findings.values() if f.is_valid]

    def expired(self) -> list:
        return [f for f in self._findings.values() if f.is_expired]

    # ── 搜索 gate ──
    def get_gates(self) -> list:
        gates = []
        for f in self.all_valid():
            gates.extend(f.gates)
        return gates

    def should_skip(self, hyp) -> tuple[bool, str]:
        """仅 SKIP 动作生效;DEPRIORITIZE 不在此短路(走 priority_adjustment)。"""
        for gate in self.get_gates():
            if gate.action == "SKIP" and gate.matches(hyp):
                return True, gate.reason
        return False, ""

    def priority_adjustment(self, hyp) -> float:
        """1.0 正常 / 0.3 降权 / 0.0 跳过。命中多 gate 取最严(最小)。"""
        adj = 1.0
        for gate in self.get_gates():
            if gate.matches(hyp):
                adj = min(adj, _PRIORITY.get(gate.action, 1.0))
        return adj

    # ── 保质期 ──
    def check_expiry(self) -> list:
        """返回需重测的结论(自身过期 + 父节点过期级联)。每轮搜索开始时调。"""
        need = []
        for f in self._findings.values():
            if f.is_expired:
                need.append(f)
                continue
            for pid in f.depends_on:
                parent = self._findings.get(pid)
                if parent and parent.is_expired:
                    need.append(f)
                    break
        return need

    # ── 从验证结果现场生长 finding ──
    def record_from_validation(
        self, hyp, passed: bool, metrics: dict,
        stage: str = "", action: Optional[str] = None, expiry_days: int = 180,
    ) -> Finding:
        """把一次验证结果转成 Finding(失败也记,避免重复尝试)。

        passed=True  → 记录通过结论,不产 gate。
        passed=False → 产 gate:phase1 合成失败默认 SKIP,其余默认 DEPRIORITIZE。
                       到期后 check_expiry 触发重测(DEPRIORITIZE 类),SKIP 类同样带保质期。
        """
        fid = f"validated_{getattr(hyp, 'id', 'unknown')}"
        tag = "✓" if passed else "✗"
        name = getattr(hyp, "name", getattr(hyp, "factor_fn_name", "?"))
        statement = (f"{tag} {name} [{stage}] "
                     f"sharpe={metrics.get('wf_sharpe', metrics.get('sharpe', 0)):.2f} "
                     f"annual={metrics.get('annual', 0):.1%}")

        gates = []
        if not passed:
            if action is None:
                action = "SKIP" if stage in _HARD_FAIL_STAGES else "DEPRIORITIZE"
            match = {"factor_fn_name": getattr(hyp, "factor_fn_name", "")}
            for k, v in (getattr(hyp, "factor_params", {}) or {}).items():
                match[str(k)] = str(v)
            reason = (f"{stage} 验证未过({statement});"
                      f"{'真坏候选,永久跳过' if action == 'SKIP' else f'{expiry_days}天后到期重测'}")
            gates.append(SearchGate(match=match, action=action, reason=reason))

        finding = Finding(
            id=fid, statement=statement, domain="factor",
            confidence=0.9 if passed else 0.8,
            evidence=[getattr(hyp, "id", "")],
            created=date.today().isoformat(),
            expires=(date.today() + timedelta(days=expiry_days)).isoformat(),
            depends_on=[], gates=gates, metrics=dict(metrics),
        )
        self.add(finding)
        return finding

    # ── 持久化 ──
    def save(self, path: str) -> None:
        data = {
            fid: {
                "id": f.id, "statement": f.statement, "domain": f.domain,
                "confidence": f.confidence, "evidence": f.evidence,
                "created": f.created, "expires": f.expires,
                "depends_on": f.depends_on, "metrics": f.metrics,
                "gates": [{"match": g.match, "action": g.action, "reason": g.reason}
                          for g in f.gates],
            }
            for fid, f in self._findings.items()
        }
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
        for fid, d in data.items():
            gates = [SearchGate(match=g["match"], action=g["action"], reason=g.get("reason", ""))
                     for g in d.get("gates", [])]
            self._findings[fid] = Finding(
                id=d["id"], statement=d["statement"], domain=d.get("domain", "factor"),
                confidence=d.get("confidence", 0.8), evidence=d.get("evidence", []),
                created=d.get("created", ""), expires=d.get("expires", ""),
                depends_on=d.get("depends_on", []), gates=gates,
                metrics=d.get("metrics", {}),
            )

    def summary(self) -> str:
        total = len(self._findings)
        valid = len(self.all_valid())
        exp = len(self.expired())
        active_gates = sum(len(f.gates) for f in self.all_valid())
        return (f"KnowledgeGraph: {total} findings "
                f"({valid} valid, {exp} expired, {active_gates} active gates)")


# 默认 store:git-tracked 的 durable 知识(对照 pending_lessons),非 data_lake 临时态
DEFAULT_STORE = os.path.join(os.path.dirname(__file__), "findings.json")


def load_graph(store_path: Optional[str] = None) -> KnowledgeGraph:
    """加载知识图谱(缺省用 knowledge/findings.json)。空文件 → 空图。"""
    return KnowledgeGraph(store_path or DEFAULT_STORE)
