"""Minimal NSGA-II search for stage 1."""
from dataclasses import dataclass
import math
import random

from factory.objectives import OBJECTIVE_DIRECTIONS, dominates, scalar_rank
from factory.search_space import Candidate, FACTOR_FAMILIES, _candidate_family


FACTOR_NAMES = [name for names in FACTOR_FAMILIES.values() for name in names]
NICHE_FAMILIES = {
    "all": list(FACTOR_FAMILIES),
    "non_size": [family for family in FACTOR_FAMILIES if family != "size"],
    "reversal_liquidity": ["reversal", "liquidity-flow", "price-location"],
    "quality_location": ["low-vol", "momentum-quality", "price-location"],
    "defensive_liquidity": ["liquidity-quality", "beta-defensive", "price-location"],
    "trend_quality": ["trend-stability", "momentum-quality", "beta-defensive"],
    "fundamental_quality": ["fundamental-quality", "fundamental-growth"],
    "fundamental_value": ["fundamental-value", "fundamental-quality"],
    "orthogonal_fundamental": ["fundamental-quality", "fundamental-growth", "fundamental-value"],
}
TOP_N_CHOICES = [15, 20, 25, 40, 60, 80, 120]
REBALANCE_CHOICES = [10, 20, 40, 60, 80]
LEVERAGE_CHOICES = [1.0, 1.25]
MAX_FACTORS = 3


def factor_pool_for_niche(niche):
    families = NICHE_FAMILIES.get(niche)
    if families is None:
        raise ValueError(f"Unsupported niche: {niche}")
    return [factor for family in families for factor in FACTOR_FAMILIES[family]]


@dataclass(frozen=True)
class Gene:
    factors: tuple[str, ...]
    weights: tuple[float, ...]
    top_n: int
    rebalance_days: int
    leverage: float

    def key(self):
        rounded = tuple(round(w, 3) for w in self.weights)
        return self.factors, rounded, self.top_n, self.rebalance_days, self.leverage


def _normalize(weights):
    total = sum(abs(w) for w in weights) or 1.0
    return tuple(round(w / total, 4) for w in weights)


def _random_gene(rng, factor_pool):
    n = rng.randint(1, MAX_FACTORS)
    factors = tuple(rng.sample(factor_pool, min(n, len(factor_pool))))
    weights = _normalize([rng.uniform(0.15, 1.0) for _ in factors])
    leverage = 1.25 if "size60" in factors and rng.random() < 0.65 else rng.choice(LEVERAGE_CHOICES)
    return Gene(
        factors=factors,
        weights=weights,
        top_n=rng.choice(TOP_N_CHOICES),
        rebalance_days=rng.choice(REBALANCE_CHOICES),
        leverage=leverage,
    )


def _repair(gene, factor_pool=None):
    factor_pool = factor_pool or FACTOR_NAMES
    pairs = []
    seen = set()
    for factor, weight in zip(gene.factors, gene.weights):
        if factor not in factor_pool or factor in seen:
            continue
        seen.add(factor)
        pairs.append((factor, abs(weight) or 0.1))
    if not pairs:
        pairs = [(factor_pool[0], 1.0)]
    pairs = pairs[:MAX_FACTORS]
    factors, weights = zip(*pairs)
    return Gene(
        factors=tuple(factors),
        weights=_normalize(weights),
        top_n=gene.top_n if gene.top_n in TOP_N_CHOICES else 25,
        rebalance_days=gene.rebalance_days if gene.rebalance_days in REBALANCE_CHOICES else 20,
        leverage=gene.leverage if gene.leverage in LEVERAGE_CHOICES else 1.0,
    )


def _mutate(gene, rng, mutation_rate, factor_pool=None):
    factor_pool = factor_pool or FACTOR_NAMES
    factors = list(gene.factors)
    weights = list(gene.weights)

    if rng.random() < mutation_rate:
        op = rng.choice(["replace", "add", "drop"])
        if op == "replace" and factors:
            factors[rng.randrange(len(factors))] = rng.choice(factor_pool)
        elif op == "add" and len(factors) < MAX_FACTORS:
            factors.append(rng.choice(factor_pool))
            weights.append(rng.uniform(0.15, 1.0))
        elif op == "drop" and len(factors) > 1:
            idx = rng.randrange(len(factors))
            factors.pop(idx)
            weights.pop(idx)

    if rng.random() < mutation_rate:
        weights = [max(0.05, w + rng.uniform(-0.35, 0.35)) for w in weights]
    if rng.random() < mutation_rate:
        top_n = rng.choice(TOP_N_CHOICES)
    else:
        top_n = gene.top_n
    if rng.random() < mutation_rate:
        rebalance_days = rng.choice(REBALANCE_CHOICES)
    else:
        rebalance_days = gene.rebalance_days
    if rng.random() < mutation_rate:
        leverage = rng.choice(LEVERAGE_CHOICES)
    else:
        leverage = gene.leverage

    return _repair(Gene(tuple(factors), tuple(weights), top_n, rebalance_days, leverage), factor_pool)


def _crossover(a, b, rng, factor_pool=None):
    factor_pool = factor_pool or FACTOR_NAMES
    factors = []
    weights = []
    for gene in [a, b]:
        for factor, weight in zip(gene.factors, gene.weights):
            if factor in factor_pool and factor not in factors and rng.random() < 0.55:
                factors.append(factor)
                weights.append(weight)
    if not factors:
        source = rng.choice([a, b])
        factors = list(source.factors)
        weights = list(source.weights)
    return _repair(Gene(
        tuple(factors[:MAX_FACTORS]),
        tuple(weights[:MAX_FACTORS]),
        rng.choice([a.top_n, b.top_n]),
        rng.choice([a.rebalance_days, b.rebalance_days]),
        rng.choice([a.leverage, b.leverage]),
    ), factor_pool)


def candidate_from_gene(gene, version):
    family = _candidate_family(gene.factors)
    desc = f"{'+'.join(gene.factors)} top{gene.top_n} reb{gene.rebalance_days} lev{gene.leverage:g}"
    return Candidate(
        family=family,
        version=version,
        desc=desc,
        factors=list(gene.factors),
        weights=list(gene.weights),
        top_n=gene.top_n,
        rebalance_days=gene.rebalance_days,
        leverage=gene.leverage,
    )


def genes_to_candidates(genes, prefix="nsga2"):
    return [candidate_from_gene(gene, f"{prefix}.{i:03d}") for i, gene in enumerate(genes, 1)]


def _objective_row(row):
    return {
        "annual": row["annual"],
        "maxdd": row["maxdd"],
        "sharpe": row["sharpe"],
        "turnover_pa": row["turnover_pa"],
        "corr_to_baseline": row["corr_to_baseline"],
    }


def _sort_value(row, key):
    value = row.get(key)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return -float("inf") if OBJECTIVE_DIRECTIONS[key] == "max" else float("inf")
    return value


def fast_non_dominated_sort(rows):
    domination_counts = [0] * len(rows)
    dominated = [set() for _ in rows]
    fronts = [[]]
    for i, row in enumerate(rows):
        for j, other in enumerate(rows):
            if i == j:
                continue
            if dominates(_objective_row(row), _objective_row(other)):
                dominated[i].add(j)
            elif dominates(_objective_row(other), _objective_row(row)):
                domination_counts[i] += 1
        if domination_counts[i] == 0:
            fronts[0].append(i)

    rank = 0
    while fronts[rank]:
        next_front = []
        for i in fronts[rank]:
            for j in dominated[i]:
                domination_counts[j] -= 1
                if domination_counts[j] == 0:
                    next_front.append(j)
        rank += 1
        fronts.append(next_front)
    return fronts[:-1]


def crowding_distance(rows, front):
    if not front:
        return {}
    distance = {idx: 0.0 for idx in front}
    keys = ["annual", "maxdd", "sharpe", "turnover_pa", "corr_to_baseline"]
    for key in keys:
        ordered = sorted(front, key=lambda idx: _sort_value(rows[idx], key))
        distance[ordered[0]] = float("inf")
        distance[ordered[-1]] = float("inf")
        low = _sort_value(rows[ordered[0]], key)
        high = _sort_value(rows[ordered[-1]], key)
        span = high - low
        if not math.isfinite(span) or span == 0:
            continue
        for pos in range(1, len(ordered) - 1):
            upper = _sort_value(rows[ordered[pos + 1]], key)
            lower = _sort_value(rows[ordered[pos - 1]], key)
            distance[ordered[pos]] += (upper - lower) / span
    return distance


def select_survivors(rows, genes, population_size):
    fronts = fast_non_dominated_sort(rows)
    survivor_pairs = []
    diagnostics = []
    for front_no, front in enumerate(fronts, 1):
        distances = crowding_distance(rows, front)
        ordered = sorted(front, key=lambda idx: (distances[idx], scalar_rank(rows[idx])), reverse=True)
        diagnostics.append({"front": front_no, "size": len(front)})
        for idx in ordered:
            if len(survivor_pairs) < population_size:
                survivor_pairs.append((genes[idx], rows[idx]))
    return survivor_pairs, diagnostics


def _tournament(survivor_pairs, rng):
    a, b = rng.sample(survivor_pairs, 2)
    return a[0] if scalar_rank(a[1]) >= scalar_rank(b[1]) else b[0]


def next_generation(rows, genes, population_size, rng, mutation_rate, niche="all"):
    factor_pool = factor_pool_for_niche(niche)
    survivor_pairs, diagnostics = select_survivors(rows, genes, population_size)
    survivors = [gene for gene, _ in survivor_pairs]
    children = []
    while len(children) < population_size:
        a = _tournament(survivor_pairs, rng)
        b = _tournament(survivor_pairs, rng)
        child = _crossover(a, b, rng, factor_pool)
        children.append(_mutate(child, rng, mutation_rate, factor_pool))
    return dedupe_genes(survivors + children), diagnostics


def initial_population(population_size, seed=42, niche="all"):
    rng = random.Random(seed)
    factor_pool = factor_pool_for_niche(niche)
    genes = []
    seen = set()
    while len(genes) < population_size:
        gene = _random_gene(rng, factor_pool)
        if gene.key() not in seen:
            genes.append(gene)
            seen.add(gene.key())
    return genes


def dedupe_genes(genes):
    out = []
    seen = set()
    for gene in genes:
        key = gene.key()
        if key in seen:
            continue
        seen.add(key)
        out.append(gene)
    return out
