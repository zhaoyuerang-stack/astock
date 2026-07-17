"""Agent 工具白名单 + 不越权分级(SPEC §9.2 / WEB_DESIGN §14.2)。

Phase 0:空白名单 + 风险分级常量。Phase 5 把 services.read/actions 注册成工具。
铁律:Agent 只能调白名单工具;中/高风险动作 requires_human_confirmation。
"""
from __future__ import annotations

# 风险分级 → 是否需人工二次确认
RISK_READONLY = "readonly"      # 解释/摘要 → 自动
RISK_LOW = "low"                # 生成报告/草稿 → 自动或轻确认
RISK_MID = "mid"                # 改参数/批量实验 → 必须确认
RISK_HIGH = "high"              # 调仓/下单/改风控规则 → 必须确认

REQUIRES_CONFIRMATION = {RISK_MID, RISK_HIGH}

def requires_confirmation(risk_level: str) -> bool:
    return risk_level in REQUIRES_CONFIRMATION


# ── Phase 5:工具注册表(services 函数 = 工具)──────────────────────────────────
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Tool:
    name: str
    risk: str
    desc: str
    fn: Optional[Callable]   # None = 仅提案不执行(高风险动作)
    args: tuple[str, ...] = ()


def tool_registry() -> dict[str, Tool]:
    """白名单工具。读类 = readonly(自动);run_backtest = mid;调仓 = high(仅提案)。

    懒导入避免模块级循环;Agent 只能调本表内工具。
    """
    from services.read import factors as fac, registry as reg
    from services.read import experiments as ex, portfolio as pf, risk as rk, state as st
    from services.read.stocks import resolve_stock_code, stock_profile
    from services.read.strategy_idea import check_strategy_idea

    def _backtest(**kw):
        from services.actions.run_backtest import run_backtest
        return run_backtest(**kw).model_dump()

    return {
        "data_quality":  Tool("data_quality", RISK_READONLY, "数据质量状态", lambda: st.data_quality().model_dump()),
        "resolve_stock_code": Tool(
            "resolve_stock_code",
            RISK_READONLY,
            "把股票名称或用户文本解析为 6 位 A 股代码；无法确认时返回 null",
            lambda query: resolve_stock_code(query),
            ("query",),
        ),
        "stock_profile": Tool(
            "stock_profile",
            RISK_READONLY,
            "读取个股价格日期、收益、估值、资金流和数据来源画像",
            lambda code: stock_profile(code),
            ("code",),
        ),
        "strategy_idea_check": Tool(
            "strategy_idea_check",
            RISK_READONLY,
            "把策略想法拆成可验证边界+系统事实(成本/数据质量/漏斗/相关家族线索);"
            "永不宣布有效、不产出伪净值",
            lambda idea: check_strategy_idea(idea),
            ("idea",),
        ),
        "market_state":  Tool("market_state", RISK_READONLY, "当前持仓/动作状态", lambda: st.market_state().model_dump()),
        "factors":       Tool("factors", RISK_READONLY, "alpha 因子家族", lambda: [f.model_dump() for f in fac.list_factors()]),
        "strategies":    Tool("strategies", RISK_READONLY, "母策略台账", lambda: [s.model_dump() for s in reg.list_strategies()]),
        "portfolio":     Tool("portfolio", RISK_READONLY, "当前/目标组合", lambda: pf.current_portfolio().model_dump()),
        "risk":          Tool("risk", RISK_READONLY, "风控评估", lambda: rk.risk_report().model_dump()),
        "experiments":   Tool("experiments", RISK_READONLY, "假设池漏斗", lambda: ex.funnel().model_dump()),
        "run_backtest":  Tool("run_backtest", RISK_MID, "跑生产口径回测(算力开销)", _backtest),
        "rebalance":     Tool("rebalance", RISK_HIGH, "调仓执行", None),  # 仅提案,系统永不自动执行
    }
