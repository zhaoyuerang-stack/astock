"""SPEC §7 八个核心数据模型(Pydantic v2)。

这是产品的 write-schema 契约。Phase 0 完整定义全部 8 个,但只**接线**
Strategy / ExperimentResult / FactorDefinition 三条;Portfolio / Risk / Control /
Agent 字段齐全但留后续 Phase 填业务。

铁律:纯 DTO,不 import 任何业务层。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── §7.1 Hypothesis ────────────────────────────────────────────────────────────
class Hypothesis(BaseModel):
    hypothesis_id: str
    name: str
    description: str = ""
    market_assumption: str = ""
    expected_mechanism: str = ""
    failure_condition: str = ""
    related_factors: list[str] = Field(default_factory=list)
    related_strategies: list[str] = Field(default_factory=list)
    status: str = "draft"  # draft|testing|validated|rejected|archived
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── §7.2 FactorDefinition ──────────────────────────────────────────────────────
class FactorDefinition(BaseModel):
    factor_id: str
    name: str
    hypothesis_id: str = ""
    formula: str = ""
    lookback_window: int = 0
    frequency: str = "daily"  # daily|weekly|monthly
    universe: str = ""
    neutralization_method: str = "none"  # none|industry|market_cap|industry_market_cap
    winsorize_method: str = ""
    standardize_method: str = ""
    direction: str = "positive"  # positive|negative
    created_at: Optional[datetime] = None


# ── §7.3 Experiment ────────────────────────────────────────────────────────────
class Experiment(BaseModel):
    experiment_id: str
    name: str
    hypothesis_id: str = ""
    factor_id: str = ""
    strategy_id: str = ""
    data_version: str = ""
    code_version: str = ""
    config_hash: str = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    parameters: dict = Field(default_factory=dict)
    status: str = "pending"  # pending|running|completed|failed|archived
    owner: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── §7.4 ExperimentResult ──────────────────────────────────────────────────────
class ExperimentResult(BaseModel):
    experiment_id: str
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    win_rate: float = 0.0
    ic_mean: float = 0.0
    rank_ic_mean: float = 0.0
    ic_ir: float = 0.0
    long_short_return: float = 0.0
    turnover: float = 0.0
    cost_adjusted_return: float = 0.0
    conclusion: str = ""
    pass_review: bool = False
    created_at: Optional[datetime] = None


# ── §7.5 Strategy ──────────────────────────────────────────────────────────────
class Strategy(BaseModel):
    strategy_id: str
    name: str
    type: str = "factor_topn"  # factor_topn|multi_factor|breakout|rotation|timing
    hypothesis_id: str = ""
    entry_rule: str = ""
    exit_rule: str = ""
    position_rule: str = ""
    stop_loss_rule: str = ""
    regime_filter: str = ""
    risk_budget: float = 0.0
    status: str = "draft"  # draft|active|paused|retired


# ── §7.6 PortfolioState ────────────────────────────────────────────────────────
class PortfolioState(BaseModel):
    portfolio_id: str
    date: Optional[date] = None
    nav: float = 0.0
    cash_ratio: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    var_95_1d: float = 0.0
    industry_exposure: dict = Field(default_factory=dict)
    factor_exposure: dict = Field(default_factory=dict)
    risk_status: str = "normal"  # normal|watch|warning|breach|stopped


# ── §7.7 ControlAction ─────────────────────────────────────────────────────────
class ControlAction(BaseModel):
    action_id: str
    date: Optional[datetime] = None
    object_type: str = ""  # data|factor|strategy|portfolio|experiment|agent
    object_id: str = ""
    trigger_state: str = ""
    action: str = ""  # increase|decrease|pause|stop|retest|archive|report|alert
    reason: str = ""
    recommendation: str = ""
    requires_confirmation: bool = True
    executed: bool = False
    executed_by: str = ""  # human|system|agent


# ── §7.8 AgentTask + §9.4 agent_output ─────────────────────────────────────────
class AgentOutput(BaseModel):
    """SPEC §9.4 结构化输出。"""
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    risk: list[str] = Field(default_factory=list)
    recommendation: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    requires_human_confirmation: bool = False


class AgentTask(BaseModel):
    task_id: str
    page_context: str = ""  # overview|data|factor|backtest|portfolio|risk|experiment|assistant|settings
    user_request: str = ""
    context_refs: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    status: str = "pending"  # pending|running|completed|failed
    output_type: str = ""  # explanation|report|recommendation|check|summary
    output: str = ""
    confidence: float = 0.0
    created_at: Optional[datetime] = None
