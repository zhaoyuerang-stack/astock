"""Phase 0 API 读/响应 DTO —— 端点实际返回的形状。

与 ``models``(产品 write-schema)分开:这里是"读出来给前端看"的视图,
可独立于持久化 schema 演进。纯 DTO,不 import 业务层。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


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
