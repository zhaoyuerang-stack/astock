"""Self-evolution loop for incubation-pool candidates.

This is a local, deterministic evolution driver. It does not call LLM APIs:
each generation mutates incubated candidate configs, audits them through the
existing review gate, then feeds the best surviving configs into the next
generation.
"""
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from factory.incubation import audit_variant_rows
from factory.search_space import FACTOR_FAMILIES, _candidate_family


FACTOR_TO_FAMILY = {
    factor: family
    for family, factors in FACTOR_FAMILIES.items()
    for factor in factors
}
TOP_N_CHOICES = [15, 20, 25, 40, 60, 80, 120, 160]
REBALANCE_CHOICES = [10, 20, 40, 60, 80, 120]
LEVERAGE_CHOICES = [1.0, 1.15, 1.25]


@dataclass(frozen=True)
class EvolutionConfig:
    input_path: str
    out_dir: str = "reports/incubation_evolution"
    generations: int = 3
    population: int = 12
    survivors: int = 6
    seed: int = 1307
    mutation_rate: float = 0.45
    max_factors: int = 3


def load_seed_rows(path):
    rows = json.loads(Path(path).read_text())
    return sorted(rows, key=lambda row: -row.get("incubation_score", -9))


def _factor_pool_for(config):
    families = {
        FACTOR_TO_FAMILY[factor]
        for factor in config.get("factors", [])
        if factor in FACTOR_TO_FAMILY
    }
    if not families:
        families = set(FACTOR_FAMILIES)
    pool = []
    for family in families:
        pool.extend(FACTOR_FAMILIES[family])
    return sorted(set(pool))


def _normalize(weights):
    total = sum(abs(weight) for weight in weights) or 1.0
    return [round(abs(weight) / total, 4) for weight in weights]


def _row_key(row):
    config = row["config"]
    return (
        tuple(config["factors"]),
        tuple(round(weight, 4) for weight in config["weights"]),
        config.get("top_n", 25),
        config.get("rebalance_days", 20),
        config.get("leverage", 1.0),
    )


def _candidate_row(config, source, generation, index):
    config = dict(config)
    config["family"] = _candidate_family(config["factors"])
    config["version"] = f"evo.g{generation}.{index:03d}"
    config["desc"] = (
        f"{'+'.join(config['factors'])} top{config['top_n']} "
        f"reb{config['rebalance_days']} lev{config['leverage']:g}"
    )
    return {
        "family": config["family"],
        "version": config["version"],
        "desc": config["desc"],
        "config": config,
        "source_desc": source.get("desc"),
        "source_version": source.get("version"),
        "source_incubation_score": source.get("incubation_score"),
        "generation": generation,
        "review_candidate": True,
    }


def mutate_config(base_config, rng, mutation_rate=0.45, max_factors=3):
    config = dict(base_config)
    factors = list(config["factors"])
    weights = list(config["weights"])
    pool = _factor_pool_for(config)

    if rng.random() < mutation_rate:
        op = rng.choice(["replace", "add", "drop"])
        if op == "replace" and factors:
            factors[rng.randrange(len(factors))] = rng.choice(pool)
        elif op == "add" and len(factors) < max_factors:
            new_factor = rng.choice(pool)
            if new_factor not in factors:
                factors.append(new_factor)
                weights.append(rng.uniform(0.2, 1.0))
        elif op == "drop" and len(factors) > 1:
            idx = rng.randrange(len(factors))
            factors.pop(idx)
            weights.pop(idx)

    if rng.random() < mutation_rate:
        weights = [max(0.05, weight + rng.uniform(-0.30, 0.30)) for weight in weights]
    if rng.random() < mutation_rate:
        config["top_n"] = rng.choice(TOP_N_CHOICES)
    else:
        config["top_n"] = config.get("top_n", 40)
    if rng.random() < mutation_rate:
        config["rebalance_days"] = rng.choice(REBALANCE_CHOICES)
    else:
        config["rebalance_days"] = config.get("rebalance_days", 60)
    if rng.random() < mutation_rate:
        config["leverage"] = rng.choice(LEVERAGE_CHOICES)
    else:
        config["leverage"] = min(config.get("leverage", 1.0), 1.25)

    pairs = []
    seen = set()
    for factor, weight in zip(factors, weights):
        if factor not in FACTOR_TO_FAMILY or factor in seen:
            continue
        seen.add(factor)
        pairs.append((factor, weight))
    if not pairs:
        factor = rng.choice(pool)
        pairs = [(factor, 1.0)]
    pairs = pairs[:max_factors]
    config["factors"] = [factor for factor, _ in pairs]
    config["weights"] = _normalize([weight for _, weight in pairs])
    return config


def build_generation(parents, generation, cfg, seen):
    rng = random.Random(cfg.seed + generation)
    rows = []
    attempts = 0
    while len(rows) < cfg.population and attempts < cfg.population * 20:
        attempts += 1
        parent = rng.choice(parents)
        base_config = parent["config"]
        mutated = mutate_config(
            base_config,
            rng,
            mutation_rate=cfg.mutation_rate,
            max_factors=cfg.max_factors,
        )
        row = _candidate_row(mutated, parent, generation, len(rows) + 1)
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def select_survivors(seed_rows, audits, limit):
    pool = list(seed_rows) + [
        row for row in audits
        if row.get("incubate") or row.get("registry_precheck")
    ]
    ranked = sorted(
        pool,
        key=lambda row: (
            not row.get("registry_precheck", False),
            not row.get("incubate", False),
            -row.get("incubation_score", -9),
        ),
    )
    survivors = []
    seen = set()
    for row in ranked:
        if "config" not in row:
            continue
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        survivors.append(row)
        if len(survivors) >= limit:
            break
    return survivors


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def run_self_evolution(cfg):
    out_root = Path(cfg.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    seed_rows = load_seed_rows(cfg.input_path)
    parents = seed_rows[:cfg.survivors]
    seen = {_row_key(row) for row in parents if "config" in row}
    all_audits = []
    summaries = []

    write_json(out_root / "config.json", asdict(cfg))
    write_json(out_root / "seeds.json", parents)

    for generation in range(1, cfg.generations + 1):
        candidates = build_generation(parents, generation, cfg, seen)
        audits = audit_variant_rows(candidates) if candidates else []
        all_audits.extend(audits)
        parents = select_survivors(seed_rows, all_audits, cfg.survivors)

        gen_dir = out_root / f"generation_{generation:02d}"
        write_json(gen_dir / "candidates.json", candidates)
        write_json(gen_dir / "audit.json", audits)
        write_json(gen_dir / "survivors.json", parents)
        summaries.append({
            "generation": generation,
            "candidates": len(candidates),
            "registry_precheck": sum(bool(row.get("registry_precheck")) for row in audits),
            "incubate": sum(bool(row.get("incubate")) for row in audits),
            "best_incubation_score": max(
                [row.get("incubation_score", -9) for row in audits],
                default=None,
            ),
            "survivors": len(parents),
        })
        write_json(out_root / "summary.json", {
            "config": asdict(cfg),
            "seed_candidates": len(seed_rows),
            "generations": summaries,
        })

    precheck = [row for row in all_audits if row.get("registry_precheck")]
    incubate = sorted(
        [row for row in all_audits if row.get("incubate")],
        key=lambda row: -row.get("incubation_score", -9),
    )
    write_json(out_root / "all_audits.json", all_audits)
    write_json(out_root / "candidate_batch.json", precheck)
    write_json(out_root / "incubation_pool.json", incubate)
    write_json(out_root / "survivors.json", parents)
    final_summary = {
        "config": asdict(cfg),
        "seed_candidates": len(seed_rows),
        "evaluated": len(all_audits),
        "registry_precheck": len(precheck),
        "incubate": len(incubate),
        "generations": summaries,
        "acceptance_met": len(precheck) >= 2,
    }
    write_json(out_root / "summary.json", final_summary)
    return final_summary, precheck, incubate
