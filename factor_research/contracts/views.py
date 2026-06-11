"""Phase 0 API 读/响应 DTO —— 端点实际返回的形状。

与 ``models``(产品 write-schema)分开:这里是"读出来给前端看"的视图,
可独立于持久化 schema 演进。纯 DTO,不 import 业务层。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from contracts.models import AgentOutput


class BacktestResult(BaseModel):
    """``services.actions.run_backtest`` 的返回。

    字段直接对应 ``core.engine.BacktestResult.metrics`` + detail 摘要,
    保证"service 结果 == strategy_lake.py"可逐项比对。
    """
    annual: float
    vol: float
    sharpe: float
    maxdd: float
    calmar: float
    hit: bool
    n: int
    turnover_annual: float
    cost_annual: float
    yearly_returns: dict[int, float] = Field(default_factory=dict)
    n_stocks: int
    n_days: int
    start: str
    end: str
    family: str = ""
    version: str = ""


class StrategyView(BaseModel):
    """registry 中一个 (family, version) 的只读视图。"""
    strategy_id: str          # f"{family}/{version}"
    family: str
    family_name: str = ""
    family_status: str = ""
    version: str = ""
    status: str = ""
    hypothesis: str = ""
    regime: str = ""
    desc: str = ""
    data_scope: dict | str = ""  # 台账里 data_scope 是结构化 dict(source/口径/指标),少数旧版本可能是字符串
    metrics: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    notes: str = ""


class FactorView(BaseModel):
    """alpha 家族(因子)的只读视图(registry 家族级派生)。"""
    name: str                 # family id
    display_name: str = ""
    hypothesis: str = ""
    regime: str = ""
    n_versions: int = 0
    status: str = ""


# ── Phase 2 状态层 ─────────────────────────────────────────────────────────────
class DataQualityView(BaseModel):
    """数据质量状态(读 data_lake/quality_report.json)。

    区分真问题与 A股正常现象(铁律#7):severe = 负价/OHLC错;
    跳变>50% 多为除权/涨跌停,单列不计入 severe。
    """
    total: int
    clean: int
    clean_ratio: float
    issue_breakdown: dict = Field(default_factory=dict)
    n_flagged: int = 0
    flagged_sample: list[dict] = Field(default_factory=list)
    severe_count: int = 0           # 真问题股票数(负价/OHLC错)
    jump_count: int = 0             # 跳变标记数(含正常现象)
    verdict: str = ""               # 可用 / 关注 / 不建议回测
    duckdb: dict | None = None      # 可选:DuckDB 即席复核


class FactorHealthView(BaseModel):
    """策略/因子健康(读 reports/factor_health.json)。"""
    name: str
    sharpe: float = 0.0
    momentum_6m: float = 0.0
    trend: str = ""


class MarketStateView(BaseModel):
    """当前持仓/动作状态(读 signals/state.json)。"""
    current_position: str = ""
    last_action: str = ""
    last_signal_date: str | None = None
    last_rebalance_date: str | None = None
    n_holdings: int = 0


# ── Phase 3 组合 / 风控 ─────────────────────────────────────────────────────────
class Holding(BaseModel):
    code: str
    weight: float


class PortfolioView(BaseModel):
    """当前组合(实盘/纸面)+ 目标组合(选股层 top-N)。"""
    nav: float = 0.0
    cash: float = 0.0
    current_positions: list[Holding] = Field(default_factory=list)
    stance: str = ""              # 当前动作(如 空仓观望)
    regime: str = ""              # bull/bear/...
    note: str = ""                # 如 BEAR→国债ETF
    target_holdings: list[Holding] = Field(default_factory=list)
    target_as_of: str | None = None
    target_note: str = ""


class RiskRuleCheck(BaseModel):
    rule: str
    threshold: float
    current: float | None = None   # None = 无法计算(如空仓/缺数据)
    status: str = "ok"             # ok | warn | breach | na
    note: str = ""


class RiskReport(BaseModel):
    """风控评估:逐条规则 + 超限生成的控制动作。"""
    evaluated_on: str = ""         # target / current
    checks: list[RiskRuleCheck] = Field(default_factory=list)
    control_actions: list[dict] = Field(default_factory=list)  # ControlAction dicts
    verdict: str = "正常"          # 正常 | 预警 | 超限


# ── Phase 4 研究实验 ────────────────────────────────────────────────────────────
class FunnelView(BaseModel):
    """假设池漏斗:DRAFTED→QUEUED→L0~L3→PROMOTED;DISCARDED/SHELVED 旁路。"""
    total: int = 0
    stages: list[dict] = Field(default_factory=list)  # [{stage, count}]
    side: list[dict] = Field(default_factory=list)
    discard_ratio: float = 0.0
    registered: int = 0


class HypothesisView(BaseModel):
    id: str
    name: str = ""
    factor_fn_name: str = ""
    factor_params: dict = Field(default_factory=dict)
    timing_fn_name: str | None = None
    status: str = ""
    source: str = ""               # mutation | llm_paper | anomaly | manual
    mechanism: str = ""
    citation: str = ""
    created_at: str = ""


class RegisteredExperimentView(BaseModel):
    """已晋级登记的实验(台账版本)+ 可复现键(config_hash)。"""
    strategy_id: str
    family_name: str = ""
    version: str = ""
    status: str = ""
    date: str = ""
    config_hash: str = ""
    config: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    data_scope: dict = Field(default_factory=dict)


class AutoResearchCandidateView(BaseModel):
    """Auto Factor Research candidate submitted as controlled JSON AST."""
    fingerprint: str
    status: str = ""
    source: str = ""
    ast: dict = Field(default_factory=dict)
    complexity_score: float = 0.0
    max_auto_stage: str = ""
    notes: str = ""
    created_at: str = ""


class AutoResearchReviewItemView(BaseModel):
    """Candidate promoted to human review. This is not LIVE registration."""
    fingerprint: str
    status: str = ""
    decision: str = ""
    reason: str = ""
    candidate: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    review_action: str = ""    # "" = 待复核;approve / reject = 已人工决策
    reviewer_notes: str = ""
    reviewed_at: str = ""


class AutoResearchReviewRequest(BaseModel):
    action: str        # approve | reject
    notes: str = ""


class AutoResearchFunnelView(BaseModel):
    """AutoResearch Lite funnel counts."""
    total: int = 0
    stages: list[dict] = Field(default_factory=list)
    review_queue: int = 0


class AutoResearchRunResultView(BaseModel):
    fingerprint: str
    status: str = ""
    decision: str = ""
    reason: str = ""
    protocols: list[str] = Field(default_factory=list)


class AutoResearchRunResponse(BaseModel):
    vintage_id: str = ""
    max_stage: str = "l0"
    results: list[AutoResearchRunResultView] = Field(default_factory=list)


class AutoResearchPromoteResponse(BaseModel):
    """APPROVED 候选 → workflow phase1~4 正式入册的结果。"""
    fingerprint: str
    hypothesis_name: str = ""
    version: str = ""
    registered: bool = False
    detail: str = ""


class AutoResearchLLMGenResponse(BaseModel):
    """LLM 生成候选并走真实验证线的结果。"""
    model: str = ""
    requested: int = 0
    accepted: int = 0
    rejected: list[str] = Field(default_factory=list)   # 每条 = 拒绝原因
    run: AutoResearchRunResponse = Field(default_factory=AutoResearchRunResponse)


class AutoResearchChampionView(BaseModel):
    fingerprint: str
    island: int = 0
    generation: int = 0
    icir: float = 0.0
    expr: str = ""
    status: str = ""
    decision: str = ""
    reason: str = ""


class AutoResearchIslandSearchResponse(BaseModel):
    """多岛屿进化搜索结果。"""
    vintage_id: str = ""
    islands: int = 0
    generations: int = 0
    evaluated: int = 0
    seeded_by: str = "seeds"        # seeds | llm
    champions: list[AutoResearchChampionView] = Field(default_factory=list)


# ── Phase 5 Agent ──────────────────────────────────────────────────────────────
class AgentAskRequest(BaseModel):
    request: str
    context: dict = Field(default_factory=dict)   # {current_page, selected_object_id, ...}


class AgentAskResponse(BaseModel):
    output: AgentOutput
    task_id: str
    tool: str | None = None
    risk: str | None = None        # 命中工具的风险级
    llm_ready: bool = False        # 是否已接真 LLM(当前规则式 = False)


# ── Phase 6 系统设置 / 审计 ─────────────────────────────────────────────────────
class SystemConfigView(BaseModel):
    cost: dict = Field(default_factory=dict)        # 含 locked=True(成本铁律只读)
    strategy: dict = Field(default_factory=dict)
    risk_policy: dict = Field(default_factory=dict)
    data: dict = Field(default_factory=dict)
    ai_model: dict = Field(default_factory=dict)
    services: list[dict] = Field(default_factory=list)
    quarantine_ranges: int = 0


class AuditEntry(BaseModel):
    kind: str = ""        # agent | control | backtest | config | review
    summary: str = ""
    detail: str = ""
    status: str = ""
    actor: str = ""       # human | system | agent


class AuditView(BaseModel):
    entries: list[AuditEntry] = Field(default_factory=list)
    total: int = 0


# ── LLM 配置(UI 可写)──────────────────────────────────────────────────────────
class LLMConfigView(BaseModel):
    """给前端的当前 LLM 配置 —— key 永不回传明文。"""
    provider: str = "none"
    model: str = ""
    base_url: str = ""
    has_key: bool = False
    key_hint: str = ""          # 形如 "sk-…ab",仅提示
    llm_ready: bool = False


class LLMConfigSet(BaseModel):
    """前端提交的配置。api_key 留空 = 保留原 key(不覆盖)。"""
    provider: str = "none"
    model: str = ""
    base_url: str = ""
    api_key: str | None = None


class LLMTestResult(BaseModel):
    ok: bool = False
    message: str = ""


# ── 模拟盘跟单(P5 债券轮动 · web 操作卡/流水/净值)────────────────────────────
class PaperTradeRow(BaseModel):
    """trades.csv 单行 —— 已成交记录。"""
    date: str = ""
    code: str = ""
    name: str = ""
    side: str = ""              # BUY | SELL
    shares: int = 0
    price: float = 0.0
    notional: float = 0.0
    cost: float = 0.0
    cash_after: float = 0.0


class PaperBlockedRow(BaseModel):
    """真实盘约束未成交(停牌/一字板/ETF 无数据)。"""
    side: str = ""
    code: str = ""
    name: str = ""
    reason: str = ""


class PaperPositionRow(BaseModel):
    code: str = ""
    name: str = ""
    shares: int = 0
    cost: float = 0.0
    price: float | None = None  # None = 停牌
    mv: float = 0.0
    pnl: float = 0.0
    asset: str = "stock"        # stock | etf


class PaperPlanItem(BaseModel):
    """明日计划单腿(参考价=信号日收盘,实际按 T+1 成交价模式)。"""
    action: str = ""            # BUY | SELL
    code: str = ""
    name: str = ""
    ref_price: float = 0.0
    est_shares: int = 0
    est_notional: float = 0.0


class BondInstructionView(BaseModel):
    """债券 ETF 轮动指令卡(P5)。"""
    active: bool = False
    side: str = ""              # BUY | SELL | HOLD | ""
    code: str = "511010"
    name: str = "国债ETF"
    ref_price: float = 0.0
    est_shares: int = 0
    est_notional: float = 0.0
    shares_held: int = 0
    note: str = ""


class TradePlanView(BaseModel):
    """今日操作卡:今日成交 + 明日计划 + 轮动指令 + 账户 + 确认状态。"""
    signal_date: str = ""
    generated_at: str = ""
    stale: bool = False
    stale_reason: str = ""
    regime: str = ""
    regime_dist: float = 0.0
    in_market: bool = False
    band_exposure: float = 0.0
    action: str = ""
    executed: list[PaperTradeRow] = Field(default_factory=list)
    blocked: list[PaperBlockedRow] = Field(default_factory=list)
    plan: list[PaperPlanItem] = Field(default_factory=list)
    bond: BondInstructionView | None = None
    positions: list[PaperPositionRow] = Field(default_factory=list)
    nav: float = 0.0
    cash: float = 0.0
    position_value: float = 0.0
    total_return: float = 0.0
    disclaimer: str = ""


class NavPoint(BaseModel):
    date: str = ""
    nav: float = 0.0
    cash: float = 0.0
    position_value: float = 0.0
    total_return: float = 0.0


class NavCurveView(BaseModel):
    points: list[NavPoint] = Field(default_factory=list)
    inception: str = ""
    init_capital: float = 0.0
    latest_nav: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0


class PaperTradesView(BaseModel):
    trades: list[PaperTradeRow] = Field(default_factory=list)
    total: int = 0
