"""多岛屿进化搜索:在受控 DSL 空间内变异/交叉/迁移。

每个岛屿独立进化(各自 rng),周期性把最优个体迁移到邻岛——岛屿模型
保多样性、防全局早熟。适应度四项(同一套 canonical 验证线,绝无第二套口径):
  |ICIR|                          真实 run_l0 的独立 edge
  + novelty_weight × 行为新颖性    vs 已评估候选+参考池的最近邻行为距离(因子形态)
  − corr_weight × 对在册组合相关    候选 top-N 收益与在册腿同涨同跌→罚,反相关(防御腿)→奖
  − turnover_weight × 换手代理      top-N 成员相邻期流失率→罚,把 L1 的成本压力前置
  [硬闸] 对在册相关 ≥ rediscovery_corr → |ICIR| 归零(边际为零,不让高 IC 重发现霸榜)
只奖绩效必然同质坍缩;新颖性填未占领的行为生态位;边际项填组合相关空洞
(伪多样性审计:在册 5 股票腿 0.76 相关);换手项防"高 IC 高换手在 L1 被成本杀"
(成本约 12pp/年),并抵消去相关项对反转(高换手)的偏好。冠军可再走更深的 L1~L3。

全程确定性:同 rng_seed + 同数据 → 同搜索轨迹(实验可复现)。
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field, replace

from .generator import generate_seed_candidates
from .models import Candidate
from .novelty import (
    candidate_factor_panel,
    partial_correlation_to_book,
    novelty_score,
    sample_behavior_dates,
    topn_long_return,
    topn_turnover,
)
from .pipeline import run_validation_pipeline
from .registry import ALLOWED_FACTORS, ALLOWED_TRANSFORMS
from .validator import DSLValidationError, validate_candidate_ast


def ast_expr(ast: dict) -> str:
    expr = " + ".join(
        f"{t.get('factor')}({t.get('params', {}).get('window', '')})×{t.get('weight', 1)}"
        for t in ast.get("terms", [])
    )
    return f"-({expr})" if ast.get("direction") == "negative" else expr


def _random_params(spec, rng: random.Random) -> dict:
    return {name: rng.randint(int(lo), int(hi)) for name, (lo, hi) in spec.params.items()}


def _random_term(rng: random.Random) -> dict:
    name = rng.choice(sorted(ALLOWED_FACTORS))
    return {
        "factor": name,
        "params": _random_params(ALLOWED_FACTORS[name], rng),
        "transforms": ["mad_clip", "zscore", "rank"],
        "weight": round(rng.uniform(0.2, 1.0) * rng.choice([1, -1]), 2),
    }


def mutate_ast(ast: dict, rng: random.Random) -> dict:
    """对 AST 施加 1~2 个白名单内的随机变异,返回新 dict(不改原对象)。"""
    out = copy.deepcopy(ast)
    terms = out.get("terms", [])
    ops = ["window", "weight", "swap_factor", "direction", "transform"]
    if len(terms) < 3:
        ops.append("add_term")
    if len(terms) > 1:
        ops.append("drop_term")

    for op in rng.sample(ops, k=rng.choice([1, 2])):
        t = rng.choice(terms)
        if op == "window":
            spec = ALLOWED_FACTORS.get(t["factor"])
            if spec and "window" in spec.params:
                lo, hi = spec.params["window"]
                cur = int(t.get("params", {}).get("window", lo))
                t.setdefault("params", {})["window"] = max(int(lo), min(int(hi), int(cur * rng.uniform(0.5, 2.0)) or int(lo)))
        elif op == "weight":
            t["weight"] = round(max(-2.0, min(2.0, float(t.get("weight", 1.0)) * rng.uniform(0.5, 1.5) * rng.choice([1, 1, -1]))), 2) or 0.3
        elif op == "swap_factor":
            name = rng.choice(sorted(ALLOWED_FACTORS))
            t["factor"] = name
            t["params"] = _random_params(ALLOWED_FACTORS[name], rng)
        elif op == "direction":
            out["direction"] = "negative" if out.get("direction", "positive") == "positive" else "positive"
        elif op == "transform":
            pool = sorted(ALLOWED_TRANSFORMS)
            tr = list(t.get("transforms", []))
            if tr and rng.random() < 0.5:
                tr.remove(rng.choice(tr))
            else:
                cand = rng.choice(pool)
                if cand not in tr:
                    tr.append(cand)
            t["transforms"] = tr
        elif op == "add_term":
            terms.append(_random_term(rng))
        elif op == "drop_term":
            terms.remove(rng.choice(terms))

    mech = str(out.get("thesis", {}).get("mechanism", "")) or "岛屿搜索变异候选"
    out["thesis"] = {"mechanism": mech, "citation": "autoresearch island search"}
    return out


def crossover_ast(a: dict, b: dict, rng: random.Random) -> dict:
    """各取部分 terms 杂交;thesis 标注双亲机制。"""
    pool = copy.deepcopy(a.get("terms", [])) + copy.deepcopy(b.get("terms", []))
    k = min(len(pool), rng.choice([1, 2, 2, 3]))
    terms = rng.sample(pool, k=k)
    mech_a = str(a.get("thesis", {}).get("mechanism", ""))[:40]
    mech_b = str(b.get("thesis", {}).get("mechanism", ""))[:40]
    return {
        "type": "linear_combo",
        "terms": terms,
        "direction": rng.choice([a.get("direction", "positive"), b.get("direction", "positive")]),
        "thesis": {"mechanism": f"杂交: {mech_a} × {mech_b}" or "岛屿搜索杂交候选",
                   "citation": "autoresearch island search"},
    }


def _merge_provenance(parents: list[Candidate]) -> dict:
    """子代(变异/交叉)继承父代种子来源(ADR-022):汇总祖先 origin + 保留 LLM 种子细节。

    任一祖先是 llm_seed → ancestor_origins 含 'llm_seed' → 晋级时触发 semantic_seed_review。
    """
    origins: set[str] = set()
    llm_ancestors: list[dict] = []
    for p in parents:
        prov = p.provenance or {}
        o = prov.get("origin")
        if o == "derived":
            origins.update(prov.get("ancestor_origins", []))
            llm_ancestors.extend(prov.get("llm_ancestors", []))
        elif o == "llm_seed":
            origins.add(o)
            llm_ancestors.append({k: prov.get(k) for k in ("theme", "model") if prov.get(k)})
        elif o:
            origins.add(o)
    out: dict = {"origin": "derived", "ancestor_origins": sorted(origins)}
    dedup = [m for i, m in enumerate(llm_ancestors) if m and m not in llm_ancestors[:i]]
    if dedup:
        out["llm_ancestors"] = dedup
    return out


def _spawn_valid(parents: list[Candidate], rng: random.Random, *, crossover: bool, retries: int = 8) -> Candidate | None:
    """变异/杂交直到产出一个能过白名单校验的候选;超过重试次数放弃。

    子代 provenance 从父代血缘继承(_merge_provenance):种子来源溯源不因进化而断链。
    """
    base_asts = [p.ast for p in parents]
    prov = _merge_provenance(parents)
    for _ in range(retries):
        try:
            if crossover and len(base_asts) >= 2:
                pa, pb = rng.sample(base_asts, k=2)
                ast = crossover_ast(pa, pb, rng)
            else:
                ast = mutate_ast(rng.choice(base_asts), rng)
            return replace(validate_candidate_ast(ast), provenance=prov)
        except DSLValidationError:
            continue
    return None


@dataclass
class ChampionRecord:
    fingerprint: str
    island: int
    generation: int
    icir: float
    expr: str
    status: str = ""
    decision: str = ""
    reason: str = ""
    novelty: float = 0.0
    fitness: float = 0.0
    corr_to_book: float = 0.0
    turnover: float = 0.0
    provenance: dict = field(default_factory=dict)  # ADR-022 种子溯源(随冠军透出供审视/晋级)
    complexity: float = 0.0


@dataclass
class IslandSearchResult:
    evaluated: int = 0
    champions: list[ChampionRecord] = field(default_factory=list)


def _style_exposure(panel, style_panels) -> float:
    """候选因子面板对 size/流动性等风格的暴露 = 平均 |截面 spearman 相关| ∈ [0,1]。

    高值 = 该候选是风格(尤其 size/流动性)的伪装 / blending 把信号拉回小盘流动性簇 →
    fitness 据此压分,使搜索保持正交。panel 与 style 面板按交集对齐(style 自动截到 panel 日期,
    walk-forward 下即 ≤cutoff 训练期,size/流动性为当期 PIT 特征、无前瞻泄露)。
    """
    import pandas as pd

    vals = []
    for s in style_panels:
        sp = s.reindex(index=panel.index, columns=panel.columns)
        cs = []
        for t in panel.index:
            a, b = panel.loc[t], sp.loc[t]
            if a.notna().sum() > 30 and b.notna().sum() > 30:
                c = a.corr(b, method="spearman")
                if pd.notna(c):
                    cs.append(abs(float(c)))
        if cs:
            vals.append(sum(cs) / len(cs))
    return sum(vals) / len(vals) if vals else 0.0


def run_island_search(
    close,
    volume,
    amount,
    forward_ret,
    *,
    vintage_id: str,
    n_islands: int = 4,
    generations: int = 3,
    population: int = 8,
    elite: int = 2,
    top_k: int = 5,
    final_stage: str = "l0",
    seeds: list[Candidate] | None = None,
    rng_seed: int = 7,
    sample_dates: int | None = 120,
    novelty_weight: float = 0.25,
    corr_weight: float = 0.0,
    turnover_weight: float = 0.0,
    complexity_weight: float = 0.0,
    directional: bool = False,
    orth_weight: float = 0.0,
    computation_time_budget: float = 10.0,
    rediscovery_corr: float = 0.5,
    reference_panels: list | None = None,
    style_panels: list | None = None,
    behavior_dates: int = 60,
    top_n: int = 25,
    repository=None,
    experiment_log=None,
    review_queue=None,
    runners: dict | None = None,
) -> IslandSearchResult:
    """N 岛屿 × G 代进化;适应度 = edge + novelty_weight×新颖性 − corr_weight×对在册组合相关
    − orth_weight×对 size/流动性风格暴露(§四修法②:把"正交"设为搜索目标,根治 blending 过拟合)。
    edge = |ICIR|(默认);directional=True 时 edge=max(ICIR,0)只奖正确方向、错号(负 ICIR)归零,
    根治进化用 neg/翻号刷分。directional=False 且 orth_weight=0 完全向后兼容。
    style_panels:[size, 流动性] 风格面板(orth_weight>0 时计;size/流动性为当期 PIT 特征,无前瞻)。

    reference_panels:在册母策略的因子面板。两种用法:
      - 新颖性(行为距离):候选因子形态与之雷同 → 压分;
      - 边际贡献(corr_weight>0):候选 top-N 收益与在册腿同涨同跌 → 罚,反相关(防御腿)→ 奖。
    传入面板必须与 close 同口径(walk-forward 下即已截断的训练面板)。
    novelty_weight=0 退回纯绩效;corr_weight=0 不计边际(向后兼容)。
    """
    # 因子面板 memo 搜索内有效:清空以隔离上一次 run / 不同数据口径(防陈旧命中)
    from factors.autoresearch_dsl import clear_factor_cache
    clear_factor_cache()

    seeds = list(seeds) if seeds else list(generate_seed_candidates(limit=max(n_islands * 2, 4)))
    pipe_kw = dict(
        close=close, volume=volume, amount=amount, forward_ret=forward_ret,
        vintage_id=vintage_id, repository=repository, experiment_log=experiment_log,
        review_queue=review_queue, runners=runners, sample_dates=sample_dates,
        computation_time_budget=computation_time_budget,
    )

    memo: dict[str, tuple[float, object]] = {}  # fingerprint -> (fitness, result)
    evaluated = 0

    # 行为档案:已评估候选的因子面板,新颖性 = 与(档案 + 外部参考池)的最近邻距离。
    # 面板即传入的(walk-forward 下已截断的)训练面板,行为距离只用历史。
    behavior_idx = sample_behavior_dates(close.index, behavior_dates)
    refs: list = [p.loc[p.index.intersection(behavior_idx)] for p in (reference_panels or [])]
    archive: dict[str, object] = {}
    # 在册腿的 top-N 收益代理(一次性预算;corr_weight>0 才需要)
    ref_returns: list = []
    market_ret: object = None
    if corr_weight > 0 and forward_ret is not None:
        ref_returns = [topn_long_return(r, forward_ret, top_n) for r in refs]
        # 根因#2:市场代理 = 全市场等权前向收益,供 partial_correlation_to_book 扣共同暴露
        market_ret = forward_ret.mean(axis=1)

    pre_evaluated_results: dict[str, object] = {}

    def fitness(candidate: Candidate, island: int, generation: int) -> float:
        nonlocal evaluated
        if candidate.fingerprint in memo:
            return memo[candidate.fingerprint][0]
        if candidate.fingerprint in pre_evaluated_results:
            result = pre_evaluated_results[candidate.fingerprint]
        else:
            result = run_validation_pipeline(candidate, max_stage="l0", **pipe_kw)
        evaluated += 1
        exps = result.metrics.get("experiments", [])
        _m0 = (exps[0].get("metrics", {}) or {}) if exps else {}
        icir = _m0.get("ICIR")  # raw,仅供报告(向后兼容,阈值口径按 raw 标定)
        # fitness edge 用 NW 重叠校正的 ICIR_nw(诚实量级),非 raw(20日前瞻重叠虚高~3.5x)。
        # 根因#3:raw ICIR 会淹没 fitness 里的 novelty/turnover 项,让搜索只追 IC 无视新颖性;
        # NW 后三项才平衡。ICIR_nw 缺失时退回 raw(见 l0_ic_scan.py)。
        edge_icir = _m0.get("ICIR_nw", icir)

        # 因子面板算一次,供新颖性(行为距离)与边际(收益相关)共用
        panel = None
        if novelty_weight > 0 or corr_weight > 0 or turnover_weight > 0 or orth_weight > 0:
            try:
                panel = candidate_factor_panel(candidate.ast, close, volume, behavior_idx)
            except Exception:
                panel = None  # 算不出因子 → 不奖不罚(L0 同样会废掉它)

        nov = 0.0
        if novelty_weight > 0 and panel is not None:
            nov = novelty_score(panel, refs + list(archive.values()))
            archive[candidate.fingerprint] = panel

        corr = 0.0
        if corr_weight > 0 and panel is not None and ref_returns:
            corr = partial_correlation_to_book(
                topn_long_return(panel, forward_ret, top_n), ref_returns, market_ret,
            )

        turn = 0.0
        if turnover_weight > 0 and panel is not None:
            turn = topn_turnover(panel, top_n)

        # Complexity penalty
        comp_val = 0.0
        if complexity_weight > 0:
            from factory.autoresearch.complexity import compute_complexity
            comp_val = float(compute_complexity(candidate).score)

        # 重发现硬闸:与在册腿相关 ≥ 阈值 = 该 edge 在册已捕获,**边际为零** →
        # 把 |ICIR| 归零(无论毛 IC 多高都不该霸占冠军席)。corr/turnover 罚仍计入,
        # 使重发现沉到所有真候选之下。WF OOS 发现:0.3 软罚压不住 0.76 IC 的 illiquidity 重发现。
        # 方向:directional 时只奖正确方向(正 ICIR),错号(负 ICIR)归零——根治进化用
        # neg/翻号刷分(如 -(holder) 与 holder 同 |ICIR|)。默认 abs(向后兼容,DSL neg 仍可翻正)。
        if edge_icir is None:
            edge = 0.0
        elif directional:
            edge = max(float(edge_icir), 0.0)
        else:
            edge = abs(float(edge_icir))  # NW 诚实量级
        if rediscovery_corr and corr_weight > 0 and ref_returns and corr >= rediscovery_corr:
            edge = 0.0
        # 正交增量:罚对 size/流动性簇的暴露——blending 若把候选拉回小盘/流动性 → 压分,
        # 逼搜索保持正交(把"正交"从事后否决变成事中搜索目标)。orth_weight=0 不计(向后兼容)。
        style_pen = 0.0
        if orth_weight > 0 and panel is not None and style_panels:
            style_pen = _style_exposure(panel, style_panels)
        priority_adjustment = float(
            (result.metrics.get("knowledge_gate", {}) or {}).get("priority_adjustment", 1.0)
        )
        fit = (edge + novelty_weight * nov - corr_weight * corr - turnover_weight * turn
               - complexity_weight * comp_val - orth_weight * style_pen) * priority_adjustment
        memo[candidate.fingerprint] = (fit, result)
        meta[candidate.fingerprint] = (island, generation, float(icir) if icir is not None else 0.0, candidate, nov, corr, turn)
        return fit

    meta: dict[str, tuple[int, int, float, Candidate, float, float, float]] = {}

    # 初始化:种子轮转分配 + 变异补满
    islands: list[list[Candidate]] = []
    for i in range(n_islands):
        rng = random.Random(rng_seed + i)
        pop: dict[str, Candidate] = {}
        base = [seeds[(i + k * n_islands) % len(seeds)] for k in range(2)]
        for c in base:
            pop.setdefault(c.fingerprint, c)
        stall = 0
        while len(pop) < population and stall < population * 4:
            child = _spawn_valid(list(pop.values()), rng, crossover=False)
            if child is None or child.fingerprint in pop:
                stall += 1
                continue
            pop[child.fingerprint] = child
        islands.append(list(pop.values()))

    rngs = [random.Random(rng_seed * 1000 + i) for i in range(n_islands)]
    migrants: list[Candidate | None] = [None] * n_islands

    for gen in range(generations):
        # 1. Apply migrants first
        for i in range(n_islands):
            if migrants[i] is not None:
                islands[i].append(migrants[i])
                migrants[i] = None

        # 2. Batch pre-evaluate all new candidates in parallel
        candidates_to_eval = [c for pop in islands for c in pop if c.fingerprint not in memo and c.fingerprint not in pre_evaluated_results]
        if candidates_to_eval:
            from concurrent.futures import ThreadPoolExecutor
            num_workers = min(len(candidates_to_eval), 8)
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                jobs = {executor.submit(run_validation_pipeline, c, max_stage="l0", **pipe_kw): c for c in candidates_to_eval}
                for fut in jobs:
                    c = jobs[fut]
                    try:
                        pre_evaluated_results[c.fingerprint] = fut.result()
                    except Exception as e:
                        print(f"[!] Error pre-evaluating candidate {c.fingerprint[:8]}: {e}")

        # 3. Evaluate and breed next generation
        for i, pop in enumerate(islands):
            ranked = sorted(pop, key=lambda c: fitness(c, i, gen), reverse=True)
            elites = ranked[: max(1, elite)]
            # 下一代 = 精英 + 精英变异/杂交后代
            nxt: dict[str, Candidate] = {c.fingerprint: c for c in elites}
            stall = 0
            while len(nxt) < population and stall < population * 4:
                child = _spawn_valid(elites, rngs[i], crossover=rngs[i].random() < 0.3)
                if child is None or child.fingerprint in nxt:
                    stall += 1
                    continue
                nxt[child.fingerprint] = child
            islands[i] = list(nxt.values())
        # 环形迁移:本岛最优 → 邻岛下一代
        for i, pop in enumerate(islands):
            best = max(pop, key=lambda c: memo.get(c.fingerprint, (0.0, None))[0])
            migrants[(i + 1) % n_islands] = best

    # Batch pre-evaluate final remaining candidates
    candidates_to_eval = [c for pop in islands for c in pop if c.fingerprint not in memo and c.fingerprint not in pre_evaluated_results]
    if candidates_to_eval:
        from concurrent.futures import ThreadPoolExecutor
        num_workers = min(len(candidates_to_eval), 8)
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            jobs = {executor.submit(run_validation_pipeline, c, max_stage="l0", **pipe_kw): c for c in candidates_to_eval}
            for fut in jobs:
                c = jobs[fut]
                try:
                    pre_evaluated_results[c.fingerprint] = fut.result()
                except Exception as e:
                    print(f"[!] Error pre-evaluating candidate {c.fingerprint[:8]}: {e}")

    # 收最后一代的遗漏评估
    for i, pop in enumerate(islands):
        for c in pop:
            fitness(c, i, generations - 1)

    ranked_all = sorted(memo.items(), key=lambda kv: kv[1][0], reverse=True)[:top_k]
    champions: list[ChampionRecord] = []
    for fp, (fit, l0_result) in ranked_all:
        island, gen, icir, candidate, nov, corr, turn = meta[fp]
        result = l0_result
        if final_stage != "l0":
            result = run_validation_pipeline(candidate, max_stage=final_stage, **pipe_kw)
        from factory.autoresearch.complexity import compute_complexity
        comp_report = compute_complexity(candidate)
        champions.append(ChampionRecord(
            fingerprint=fp, island=island, generation=gen, icir=icir,
            expr=ast_expr(candidate.ast),
            status=result.status.value, decision=result.decision.value, reason=result.reason,
            novelty=nov, fitness=fit, corr_to_book=corr, turnover=turn,
            provenance=dict(candidate.provenance or {}),
            complexity=float(comp_report.score),
        ))
    return IslandSearchResult(evaluated=evaluated, champions=champions)
