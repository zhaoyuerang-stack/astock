"""Agent planner —— 把"请求 + 页面上下文"路由到白名单工具,产出结构化 AgentOutput。

不越权铁律(SPEC §9.2):
- readonly 工具 → 自动执行并解读。
- mid/high 工具(回测/调仓)→ **不执行**,返回 requires_human_confirmation 的提案。
- Agent 只能调 tool_registry 白名单;绝不直写台账/下单。

LLM 是可插拔大脑(llm_adapter):有 key 时 route() 走真推理;当前走确定性关键词+页面路由。
每次产出落 AgentTask 审计(data_lake/agent/agent_tasks.jsonl)。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from contracts.models import AgentOutput, AgentTask
from services.agent.llm_adapter import get_adapter, llm_ready
from services.agent.tools import requires_confirmation, tool_registry

ROOT = Path(__file__).resolve().parents[2]
_TASK_LOG = ROOT / "data_lake" / "agent" / "agent_tasks.jsonl"

_KEYWORD_TOOL = [
    (("数据", "质量", "脏", "缺失", "quality"), "data_quality"),
    (("因子", "alpha", "ic"), "factors"),
    (("策略", "台账", "母策略"), "strategies"),
    (("组合", "持仓", "仓位"), "portfolio"),
    (("风险", "风控", "回撤", "超限", "var"), "risk"),
    (("实验", "假设", "漏斗", "候选"), "experiments"),
    (("回测", "backtest", "复测"), "run_backtest"),
    (("调仓", "下单", "执行", "卖出", "买入", "降仓"), "rebalance"),
]
_PAGE_DEFAULT = {
    "data": "data_quality", "factors": "factors", "backtest": "run_backtest",
    "portfolio": "portfolio", "risk": "risk", "experiments": "experiments",
    "overview": "strategies",
}


def _route(request: str, context: dict, tools: dict) -> str | None:
    r = (request or "").lower()
    for kws, tool in _KEYWORD_TOOL:
        if any(k.lower() in r for k in kws):
            return tool
    via = get_adapter().route(request, context, list(tools))   # LLM 只处理关键词无法覆盖的模糊请求
    if via in tools:
        return via
    return _PAGE_DEFAULT.get(context.get("current_page", ""))


def _task_id(request: str, context: dict) -> str:
    return "t-" + hashlib.sha1(f"{request}|{context.get('current_page','')}".encode()).hexdigest()[:10]


def _log_task(task: AgentTask) -> None:
    try:
        _TASK_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _TASK_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(task.model_dump(), ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


# ── 各工具结果 → 结构化解读 ────────────────────────────────────────────────────
def _summarize(tool_name: str, data) -> AgentOutput:
    if tool_name == "data_quality":
        return AgentOutput(
            summary=f"数据质量「{data['verdict']}」:全市场 {data['total']} 只,真问题 {data['severe_count']} 只,跳变 {data['jump_count']}(多为除权/涨跌停)。",
            evidence=[f"clean {data['clean']}/{data['total']}", f"DuckDB 复核负价 {data.get('duckdb',{}).get('nonpositive_close','?')} 行"],
            risk=[f"{data['severe_count']} 只真问题需隔离/修复"] if data["severe_count"] else [],
            recommendation=["跳变不等于脏数据,勿据 clean_ratio 误判"],
            confidence=0.9)
    if tool_name == "risk":
        breaches = [c["rule"] for c in data["checks"] if c["status"] == "breach"]
        warns = [c["rule"] for c in data["checks"] if c["status"] == "warn"]
        return AgentOutput(
            summary=f"风控判定「{data['verdict']}」,{len(data['control_actions'])} 项控制动作待确认。",
            evidence=[f"{c['rule']}: {c['current']}/{c['threshold']} → {c['status']}" for c in data["checks"]],
            risk=[f"{b} 超限" for b in breaches] + [f"{w} 接近阈值" for w in warns],
            recommendation=[a["recommendation"] for a in data["control_actions"]],
            confidence=0.9)
    if tool_name == "portfolio":
        return AgentOutput(
            summary=f"当前 {data['stance']}({data['regime']});现金 {data['cash']/10000:.0f}万,持仓 {len(data['current_positions'])} 只;目标 {len(data['target_holdings'])} 只。",
            evidence=[data.get("note", ""), data.get("target_note", "")],
            recommendation=["调仓前过风控页"], confidence=0.85)
    if tool_name == "factors":
        return AgentOutput(summary=f"台账 {len(data)} 个 alpha 家族:" + "、".join(d["name"] for d in data),
                           evidence=[f"{d['display_name'] or d['name']}({d['n_versions']}版本)" for d in data], confidence=0.85)
    if tool_name == "strategies":
        live = [s for s in data if s["status"] == "在册"]
        return AgentOutput(summary=f"台账 {len(data)} 个版本,在册 {len(live)}。",
                           evidence=[f"{s['strategy_id']}: {s['status']}" for s in data[:8]], confidence=0.85)
    if tool_name == "experiments":
        return AgentOutput(
            summary=f"假设池 {data['total']} 候选,淘汰率 {data['discard_ratio']:.0%},已登记 {data['registered']}。",
            evidence=[f"{s['stage']}: {s['count']}" for s in data["stages"]], confidence=0.85)
    return AgentOutput(summary=str(data)[:300], confidence=0.5)


def _help(context: dict) -> AgentOutput:
    return AgentOutput(
        summary="我是研究副驾驶(当前规则式;给 ANTHROPIC_API_KEY 即接真 LLM)。可问:数据质量 / 因子 / 策略台账 / 组合 / 风控 / 实验 / 回测。",
        next_actions=["试问「当前风控如何」「数据质量怎样」「假设池漏斗」"],
        confidence=0.6)


def ask(request: str, context: dict | None = None) -> dict:
    """返回 {output: AgentOutput, task_id, tool, risk, llm_ready}。"""
    context = context or {}
    tools = tool_registry()
    task = AgentTask(task_id=_task_id(request, context),
                     page_context=context.get("current_page", ""),
                     user_request=request, status="running")

    tool_name = _route(request, context, tools)
    tool = tools.get(tool_name) if tool_name else None

    if tool is None:
        out = _help(context)
        task.output_type = "summary"
    elif requires_confirmation(tool.risk):
        # 不越权:不执行,返回提案
        out = AgentOutput(
            summary=f"「{tool.desc}」属 {tool.risk} 风险动作,需人工二次确认后才执行——Agent 不自动执行。",
            recommendation=[f"如确认,请在对应页面手动触发 {tool.name}"],
            risk=["高风险动作默认不执行"] if tool.risk == "high" else [],
            requires_human_confirmation=True, confidence=0.9)
        task.output_type = "recommendation"
        task.tools_used = [tool.name]
    else:
        try:
            data = tool.fn()
            out = _summarize(tool.name, data)
            # LLM(若接入)只改写 summary 文字;evidence/risk/数字仍确定性 grounded
            adapter = get_adapter()
            if adapter.available():
                prose = adapter.synthesize(request, context, tool.name, data)
                if prose:
                    if tool.name == "data_quality" and "数据质量" not in prose:
                        prose = f"数据质量: {prose}"
                    out.summary = prose
            task.tools_used = [tool.name]
            task.output_type = "explanation"
        except Exception as e:  # noqa: BLE001
            out = AgentOutput(summary=f"工具 {tool.name} 执行失败:{e}", confidence=0.3)

    task.status = "completed"
    task.output = out.summary
    task.confidence = out.confidence
    _log_task(task)
    return {"output": out.model_dump(), "task_id": task.task_id,
            "tool": tool_name, "risk": tool.risk if tool else None, "llm_ready": llm_ready()}
