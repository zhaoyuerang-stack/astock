"""多岛屿搜索编排:LLM(可选)按主题给各岛播种 → factory 岛屿进化引擎。

LLM 不可用时退回确定性种子 + 变异(seeded_by 字段如实标注,不伪装)。
适应度与验证全部走 canonical 验证线,本模块不引入任何第二套口径。
"""
from __future__ import annotations

from datetime import date

from contracts.views import AutoResearchChampionView, AutoResearchIslandSearchResponse
from factory.autoresearch import CandidateRepository
from factory.autoresearch.islands import run_island_search

from .autoresearch import _load_validation_data
from .autoresearch_llm import generate_llm_candidates

_ISLAND_THEMES = [
    "动量与趋势延续",
    "价值与基本面质量",
    "流动性与微观结构(Amihud 类)",
    "波动率与风险溢价",
]


def run_autoresearch_island_search(
    *,
    islands: int = 4,
    generations: int = 3,
    population: int = 8,
    top_k: int = 5,
    final_stage: str = "l0",
    use_llm: bool = True,
    start: str = "2018-01-01",
    sample_dates: int | None = 120,
    rng_seed: int = 7,
    repository: CandidateRepository | None = None,
    experiment_log=None,
    review_queue=None,
    adapter=None,
    close=None,
    volume=None,
    amount=None,
    forward_ret=None,
    vintage_id: str | None = None,
) -> AutoResearchIslandSearchResponse:
    if close is None or volume is None or amount is None or forward_ret is None:
        close, volume, amount, forward_ret = _load_validation_data(start)
    vintage = vintage_id or f"data_lake:{start}:{date.today().isoformat()}"
    repository = repository or CandidateRepository()

    seeds, seeded_by = [], "seeds"
    if use_llm:
        try:
            for i in range(islands):
                theme = _ISLAND_THEMES[i % len(_ISLAND_THEMES)]
                accepted, _, _ = generate_llm_candidates(
                    n=2, theme=theme, adapter=adapter, repository=repository
                )
                seeds.extend(accepted)
            if seeds:
                seeded_by = "llm"
        except ValueError:
            seeds = []  # LLM 未配置 → 确定性种子,seeded_by 保持 "seeds"

    result = run_island_search(
        close, volume, amount, forward_ret,
        vintage_id=vintage,
        n_islands=islands,
        generations=generations,
        population=population,
        top_k=top_k,
        final_stage=final_stage,
        seeds=seeds or None,
        rng_seed=rng_seed,
        sample_dates=sample_dates,
        repository=repository,
        experiment_log=experiment_log,
        review_queue=review_queue,
    )
    return AutoResearchIslandSearchResponse(
        vintage_id=vintage,
        islands=islands,
        generations=generations,
        evaluated=result.evaluated,
        seeded_by=seeded_by,
        champions=[
            AutoResearchChampionView(
                fingerprint=c.fingerprint, island=c.island, generation=c.generation,
                icir=c.icir, expr=c.expr, status=c.status, decision=c.decision, reason=c.reason,
            )
            for c in result.champions
        ],
    )
