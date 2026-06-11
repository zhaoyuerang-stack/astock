"""多岛屿进化搜索:在受控 DSL 空间内变异/交叉/迁移。

每个岛屿独立进化(各自 rng),周期性把最优个体迁移到邻岛——岛屿模型
保多样性、防全局早熟。适应度 = 真实 run_l0 的 |ICIR|(同一套 canonical
验证线,绝无第二套口径);冠军可再走更深的 L1~L3。

全程确定性:同 rng_seed + 同数据 → 同搜索轨迹(实验可复现)。
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from .generator import generate_seed_candidates
from .models import Candidate
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


def _spawn_valid(base_asts: list[dict], rng: random.Random, *, crossover: bool, retries: int = 8) -> Candidate | None:
    """变异/杂交直到产出一个能过白名单校验的候选;超过重试次数放弃。"""
    for _ in range(retries):
        try:
            if crossover and len(base_asts) >= 2:
                pa, pb = rng.sample(base_asts, k=2)
                ast = crossover_ast(pa, pb, rng)
            else:
                ast = mutate_ast(rng.choice(base_asts), rng)
            return validate_candidate_ast(ast)
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


@dataclass
class IslandSearchResult:
    evaluated: int = 0
    champions: list[ChampionRecord] = field(default_factory=list)


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
    repository=None,
    experiment_log=None,
    review_queue=None,
    runners: dict | None = None,
) -> IslandSearchResult:
    """N 岛屿 × G 代进化;适应度 = 真实 L0 |ICIR|;top_k 冠军走 final_stage。"""
    seeds = list(seeds) if seeds else list(generate_seed_candidates(limit=max(n_islands * 2, 4)))
    pipe_kw = dict(
        close=close, volume=volume, amount=amount, forward_ret=forward_ret,
        vintage_id=vintage_id, repository=repository, experiment_log=experiment_log,
        review_queue=review_queue, runners=runners, sample_dates=sample_dates,
    )

    memo: dict[str, tuple[float, object]] = {}  # fingerprint -> (fitness, result)
    evaluated = 0

    def fitness(candidate: Candidate, island: int, generation: int) -> float:
        nonlocal evaluated
        if candidate.fingerprint in memo:
            return memo[candidate.fingerprint][0]
        result = run_validation_pipeline(candidate, max_stage="l0", **pipe_kw)
        evaluated += 1
        exps = result.metrics.get("experiments", [])
        icir = (exps[0].get("metrics", {}) or {}).get("ICIR") if exps else None
        fit = abs(float(icir)) if icir is not None else 0.0
        memo[candidate.fingerprint] = (fit, result)
        meta[candidate.fingerprint] = (island, generation, float(icir) if icir is not None else 0.0, candidate)
        return fit

    meta: dict[str, tuple[int, int, float, Candidate]] = {}

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
            child = _spawn_valid([c.ast for c in pop.values()], rng, crossover=False)
            if child is None or child.fingerprint in pop:
                stall += 1
                continue
            pop[child.fingerprint] = child
        islands.append(list(pop.values()))

    rngs = [random.Random(rng_seed * 1000 + i) for i in range(n_islands)]
    migrants: list[Candidate | None] = [None] * n_islands

    for gen in range(generations):
        for i, pop in enumerate(islands):
            if migrants[i] is not None:
                pop.append(migrants[i])
                migrants[i] = None
            ranked = sorted(pop, key=lambda c: fitness(c, i, gen), reverse=True)
            elites = ranked[: max(1, elite)]
            # 下一代 = 精英 + 精英变异/杂交后代
            nxt: dict[str, Candidate] = {c.fingerprint: c for c in elites}
            base_asts = [c.ast for c in elites]
            stall = 0
            while len(nxt) < population and stall < population * 4:
                child = _spawn_valid(base_asts, rngs[i], crossover=rngs[i].random() < 0.3)
                if child is None or child.fingerprint in nxt:
                    stall += 1
                    continue
                nxt[child.fingerprint] = child
            islands[i] = list(nxt.values())
        # 环形迁移:本岛最优 → 邻岛下一代
        for i, pop in enumerate(islands):
            best = max(pop, key=lambda c: memo.get(c.fingerprint, (0.0, None))[0])
            migrants[(i + 1) % n_islands] = best

    # 收最后一代的遗漏评估
    for i, pop in enumerate(islands):
        for c in pop:
            fitness(c, i, generations - 1)

    ranked_all = sorted(memo.items(), key=lambda kv: kv[1][0], reverse=True)[:top_k]
    champions: list[ChampionRecord] = []
    for fp, (fit, l0_result) in ranked_all:
        island, gen, icir, candidate = meta[fp]
        result = l0_result
        if final_stage != "l0":
            result = run_validation_pipeline(candidate, max_stage=final_stage, **pipe_kw)
        champions.append(ChampionRecord(
            fingerprint=fp, island=island, generation=gen, icir=icir,
            expr=ast_expr(candidate.ast),
            status=result.status.value, decision=result.decision.value, reason=result.reason,
        ))
    return IslandSearchResult(evaluated=evaluated, champions=champions)
