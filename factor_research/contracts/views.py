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
