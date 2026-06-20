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
import re
from pathlib import Path

from contracts.models import AgentTask
from services.agent.llm_adapter import get_adapter
from services.agent.skills import route_skill

ROOT = Path(__file__).resolve().parents[2]
_TASK_LOG = ROOT / "data_lake" / "agent" / "agent_tasks.jsonl"

_KEYWORD_TOOL = [
    (("个股", "股票", "股价", "行情", "代码"), "stock_profile"),
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
_GROUND_TRUTH_SUMMARY_TOOLS = {
    "data_quality",
    "factors",
    "strategies",
    "portfolio",
    "risk",
    "experiments",
    "stock_profile",
}


def _route(request: str, context: dict, tools: dict) -> str | None:
    r = (request or "").lower()
    if _extract_stock_code(request):
        return "stock_profile"
    if any(k in r for k in ("怎么用", "如何使用", "使用", "说明", "手册", "工具", "页面", "导航")):
        return None
    if any(k in r for k in ("为什么", "为何", "不能", "不可以", "规则", "边界")) and any(
        k in r for k in ("下单", "买入", "卖出", "调仓", "交易")
    ):
        return None
    for kws, tool in _KEYWORD_TOOL:
        if any(k.lower() in r for k in kws):
            return tool
    via = get_adapter().route(request, context, list(tools))   # LLM 只处理关键词无法覆盖的模糊请求
    if via in tools:
        return via
    return _PAGE_DEFAULT.get(context.get("current_page", ""))


def _extract_stock_code(request: str) -> str | None:
    m = re.search(r"(?<!\d)(\d{6})(?:\.(?:sh|sz|SH|SZ))?(?!\d)", request or "")
    return m.group(1) if m else None


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
def _wants_best_strategy(request: str) -> bool:
    r = request or ""
    return any(k in r for k in ("哪个", "哪一个", "最好", "最佳", "最强", "第一", "排名"))


def _summarize(tool_name: str, data, request: str = "") -> AgentOutput:
    if tool_name == "data_quality":
        return AgentOutput(
            summary=f"数据质量「{data['verdict']}」:全市场 {data['total']} 只,真问题 {data['severe_count']} 只,跳变 {data['jump_count']}(多为除权/涨跌停)。",
            evidence=[f"clean {data['clean']}/{data['total']}", f"DuckDB 复核负价 {data.get('duckdb',{}).get('nonpositive_close','?')} 行"],
            risk=[f"{data['severe_count']} 只真问题需隔离/修复"] if data["severe_count"] else [],
            recommendation=["跳变不等于脏数据,勿据 clean_ratio 误判"],
            confidence=0.9)
    if tool_name == "stock_profile":
        px = data.get("latest_price", {})
        rets = data.get("returns", {})
        basic = data.get("daily_basic", {})
        mf = data.get("moneyflow", {})
        evidence = [
            f"最新交易日 {px.get('date')}, 收盘 {px.get('close')}",
            f"20日收益 {rets.get('ret_20d'):.2%}" if rets.get("ret_20d") is not None else "20日收益缺数据",
            f"60日收益 {rets.get('ret_60d'):.2%}" if rets.get("ret_60d") is not None else "60日收益缺数据",
        ]
        if basic:
            evidence.append(f"PE_TTM {basic.get('pe_ttm')}, PB {basic.get('pb')}, 总市值 {basic.get('total_mv')}")
        if mf:
            evidence.append(f"最新资金流净额 {mf.get('net_mf_amount')}")
        return AgentOutput(
            summary=f"{data.get('code')} {data.get('name')} 最新收盘 {px.get('close')}({px.get('date')})。",
            evidence=evidence,
            recommendation=["这是数据画像,不构成买卖建议"],
            confidence=0.9,
        )
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
        if _wants_best_strategy(request):
            ranked = sorted(
                live,
                key=lambda s: (
                    float((s.get("metrics") or {}).get("sharpe") or 0.0),
                    float((s.get("metrics") or {}).get("calmar") or 0.0),
                    float((s.get("metrics") or {}).get("annual") or 0.0),
                ),
                reverse=True,
            )
            if ranked:
                best = ranked[0]
                m = best.get("metrics") or {}
                return AgentOutput(
                    summary=(
                        f"默认按夏普排序,当前在册策略里最佳是 {best['strategy_id']}: "
                        f"年化 {float(m.get('annual') or 0.0):.2%}, "
                        f"最大回撤 {float(m.get('maxdd') or 0.0):.2%}, "
                        f"夏普 {float(m.get('sharpe') or 0.0):.2f}, "
                        f"卡玛 {float(m.get('calmar') or 0.0):.2f}。"
                    ),
                    evidence=[
                        f"{s['strategy_id']}: sharpe={(s.get('metrics') or {}).get('sharpe')}, calmar={(s.get('metrics') or {}).get('calmar')}"
                        for s in ranked[:5]
                    ],
                    recommendation=["“最好”口径可改为按夏普、卡玛、回撤或样本外 WF 指标排序"],
                    confidence=0.9,
                )
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


def _navigation_for(tool_name: str | None, context: dict) -> list[str]:
    if tool_name == "data_quality":
        return ["/data"]
    if tool_name == "stock_profile":
        return ["/data"]
    if tool_name == "risk":
        return ["/risk"]
    if tool_name == "portfolio":
        return ["/portfolio"]
    if tool_name == "experiments":
        return ["/experiments"]
    if tool_name in {"factors", "strategies"}:
        return ["/experiments"]
    if tool_name == "run_backtest":
        return ["/experiments"]
    if tool_name == "rebalance":
        return ["/trade-readiness", "/portfolio"]
    page = context.get("current_page", "")
    return [f"/{page}"] if page else []


def _attach_sources(out: AgentOutput, request: str, tool_name: str | None, context: dict) -> AgentOutput:
    if tool_name in _GROUND_TRUTH_SUMMARY_TOOLS:
        out.citations = []
        out.source_types = sorted({"runtime", "ui_context"} if context else {"runtime"})
        out.suggested_navigation = _navigation_for(tool_name, context)
        return out
    hits = retrieve_knowledge(request, limit=4)
    out.citations = [AgentCitation(**citation_from_hit(h)) for h in hits]
    source_types = {h.source_type for h in hits}
    if tool_name:
        source_types.add("runtime")
    if context:
        source_types.add("ui_context")
    out.source_types = sorted(source_types)
    out.suggested_navigation = _navigation_for(tool_name, context)
    return out


def ask(request: str, context: dict | None = None) -> dict:
    """返回 {output: AgentOutput, task_id, tool, risk, llm_ready}。"""
    context = context or {}
    task = AgentTask(task_id=_task_id(request, context),
                     page_context=context.get("current_page", ""),
                     user_request=request, status="running")
    skill = route_skill(request, context)
    result = skill.answer(request, context)
    out = result["output"]
    tool_name = result.get("tool")
    if tool_name:
        task.tools_used = [tool_name]
    task.output_type = "explanation"
    task.status = "completed"
    task.output = out.summary
    task.confidence = out.confidence
    task.context_refs = [c.source_path for c in out.citations]
    _log_task(task)
    return {"output": out.model_dump(), "task_id": task.task_id,
            "tool": tool_name, "risk": result.get("risk"), "llm_ready": result.get("llm_ready", False)}
