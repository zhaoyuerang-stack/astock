"""审计日志(SPEC §12.2):关键动作可审计。

Phase 6 来源:Agent 任务(data_lake/agent/agent_tasks.jsonl,Phase 5 落盘)+
当前风控控制动作(live)。后续阶段把回测/调仓/配置变更也纳入同一审计流。
"""
from __future__ import annotations

import json
from pathlib import Path

from contracts.views import AuditEntry, AuditView

ROOT = Path(__file__).resolve().parents[2]
_TASK_LOG = ROOT / "data_lake" / "agent" / "agent_tasks.jsonl"


def recent_audit(limit: int = 40) -> AuditView:
    entries: list[AuditEntry] = []

    # Agent 任务(倒序)
    if _TASK_LOG.exists():
        lines = [l for l in _TASK_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
        for l in reversed(lines[-limit:]):
            try:
                t = json.loads(l)
            except ValueError:
                continue
            entries.append(AuditEntry(
                kind="agent",
                summary=t.get("user_request", "")[:60] or "(空)",
                detail=f"工具 {','.join(t.get('tools_used', []) or []) or '—'} · {t.get('output_type','')}",
                status=t.get("status", ""),
                actor="agent",
            ))

    # 当前风控控制动作(live)
    try:
        from services.read.risk import risk_report
        for a in risk_report().control_actions:
            entries.append(AuditEntry(
                kind="control",
                summary=a.get("reason", ""),
                detail=a.get("trigger_state", ""),
                status="待确认" if a.get("requires_confirmation") else "—",
                actor="system",
            ))
    except Exception:  # noqa: BLE001
        pass

    return AuditView(entries=entries[:limit], total=len(entries))
