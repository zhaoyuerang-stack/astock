"""Island orchestration for phase-1 multi-objective factory search."""
from dataclasses import asdict, dataclass
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from factory.evaluator import prepare_context, run_candidate_returns
from factory.niches import annotate_niches
from factory.objectives import dominates
from factory.review import candidate_from_config, write_audit
from factory.run_factory import run_nsga2


@dataclass(frozen=True)
class IslandSpec:
    name: str
    niche: str
    seed: int
    population: int
    generations: int
    mutation_rate: float = 0.35
    review_corr: float = 0.90
    hypothesis: str = ""


DEFAULT_ISLANDS = [
    IslandSpec(
        name="reversal_liquidity_a",
        niche="reversal_liquidity",
        seed=101,
        population=8,
        generations=2,
        hypothesis="Non-size mean reversion mixed with liquidity neglect.",
    ),
    IslandSpec(
        name="quality_location_a",
        niche="quality_location",
        seed=211,
        population=8,
        generations=2,
        hypothesis="Non-size quality and price-location regime recovery.",
    ),
    IslandSpec(
        name="non_size_a",
        niche="non_size",
        seed=307,
        population=8,
        generations=2,
        hypothesis="Broad non-size alternative alpha pool.",
    ),
]


def small_islands(population=4, generations=1):
    return [
        IslandSpec(
            name="reversal_liquidity_smoke",
            niche="reversal_liquidity",
            seed=101,
            population=population,
            generations=generations,
            hypothesis="Smoke island for non-size reversal/liquidity.",
        ),
        IslandSpec(
            name="quality_location_smoke",
            niche="quality_location",
            seed=211,
            population=population,
            generations=generations,
            hypothesis="Smoke island for non-size quality/location.",
        ),
    ]


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _args_for_island(spec, start):
    return SimpleNamespace(
        start=start,
        population=spec.population,
        generations=spec.generations,
        mutation_rate=spec.mutation_rate,
        seed=spec.seed,
        niche=spec.niche,
        review_corr=spec.review_corr,
    )


def ensure_worktree(spec, worktree_root=".worktrees"):
    """Create an optional git worktree for island code isolation.

    Searches still run from the main workspace because data_lake is ignored and
    not present in fresh worktrees. The worktree is a reproducibility anchor for
    island-specific code experiments when needed.
    """
    root = Path(worktree_root)
    path = root / spec.name
    if path.exists():
        return str(path)
    branch = f"island/{spec.name}"
    root.mkdir(parents=True, exist_ok=True)
    existing = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    cmd = ["git", "worktree", "add"]
    if existing.returncode != 0:
        cmd += ["-b", branch]
    cmd += [str(path), branch if existing.returncode == 0 else "HEAD"]
    subprocess.run(cmd, check=True)
    return str(path)


def run_island(spec, start="2018-01-01", out_dir="reports/islands", create_worktree=False):
    out_root = Path(out_dir) / spec.name
    worktree_path = ensure_worktree(spec) if create_worktree else None

    ranked, history = run_nsga2(_args_for_island(spec, start))
    ranked = [
        {**row, "island": spec.name, "island_hypothesis": spec.hypothesis}
        for row in ranked
    ]
    ranked = annotate_niches(ranked, max_corr=spec.review_corr)
    review_rows = [row for row in ranked if row.get("review_candidate")]

    report_path = out_root / "front.json"
    history_path = out_root / "history.json"
    review_path = out_root / "review.json"
    audit_path = out_root / "audit.json"
    manifest_path = out_root / "manifest.json"
    _write_json(report_path, ranked)
    _write_json(history_path, history)
    _write_json(review_path, review_rows)
    _, audits = write_audit(review_path, output_path=audit_path)

    manifest = {
        "island": asdict(spec),
        "start": start,
        "worktree": worktree_path,
        "evaluated": len(ranked),
        "review_candidates": len(review_rows),
        "registry_precheck": sum(bool(row.get("registry_precheck")) for row in audits),
        "outputs": {
            "front": str(report_path),
            "history": str(history_path),
            "review": str(review_path),
            "audit": str(audit_path),
        },
    }
    _write_json(manifest_path, manifest)
    return manifest, audits


def _audit_objective(row):
    return {
        "annual": row.get("in_sample_annual"),
        "maxdd": row.get("in_sample_maxdd"),
        "sharpe": row.get("in_sample_sharpe"),
        "turnover_pa": row.get("in_sample_turnover_pa"),
        "corr_to_baseline": row.get("source_corr_to_baseline"),
    }


def audit_pareto(rows):
    rows = [row for row in rows if row.get("registry_precheck")]
    front = []
    for i, row in enumerate(rows):
        if not any(
            dominates(_audit_objective(other), _audit_objective(row))
            for j, other in enumerate(rows)
            if i != j
        ):
            front.append(row)
    return sorted(front, key=lambda row: (-row.get("in_sample_annual", -9), row.get("source_corr_to_baseline", 9)))


def aggregate_islands(manifests, audits, out_dir="reports/islands"):
    out_root = Path(out_dir)
    precheck = [row for row in audits if row.get("registry_precheck")]
    incubation = sorted(
        [row for row in audits if row.get("incubate")],
        key=lambda row: -row.get("incubation_score", -9),
    )
    front = audit_pareto(precheck)
    annotate_pairwise_correlation(front)
    summary = {
        "islands": manifests,
        "total_registry_precheck": len(precheck),
        "total_incubate": len(incubation),
        "pareto_candidates": len(front),
        "acceptance_met": _acceptance_met(front),
    }
    _write_json(out_root / "summary.json", summary)
    _write_json(out_root / "candidate_batch.json", front)
    _write_json(out_root / "incubation_pool.json", incubation)
    return summary, front


def annotate_pairwise_correlation(front, start="2018-01-01"):
    if len(front) < 2:
        for row in front:
            row["pairwise_corr_max"] = None
        return front
    close, amount, library, _ = prepare_context(start)
    returns = []
    for i, row in enumerate(front, 1):
        candidate = candidate_from_config(row["config"], f"front.{i:03d}")
        ret, _ = run_candidate_returns(candidate, close, amount, library, start)
        returns.append(ret)
    for i, row in enumerate(front):
        corrs = []
        for j, other in enumerate(returns):
            if i == j:
                continue
            common = returns[i].index.intersection(other.index)
            if len(common) > 100:
                corrs.append(float(returns[i].loc[common].corr(other.loc[common])))
        row["pairwise_corr_max"] = max(corrs) if corrs else None
    return front


def _acceptance_met(front):
    niches = {row.get("niche") for row in front if row.get("size_exposure", 1) < 1}
    low_corr = [
        row for row in front
        if row.get("pairwise_corr_max") is not None
        and abs(row.get("pairwise_corr_max")) < 0.85
    ]
    return len(front) >= 2 and len(niches) >= 2 and len(low_corr) >= 2
