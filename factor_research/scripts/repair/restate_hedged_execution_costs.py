"""Recompute and restate the six hedged-family versions affected by R-COST-001.

The historical implementations charged hedge borrow/switch friction but set the
long stock leg's execution costs to zero.  This repair always reruns the actual
strategy implementations with ``core.engine.CostModel`` defaults, excludes the
holdout vault from selection evidence, and updates the registry only through
``strategy_registry.restate_execution_costs``.

Default mode is dry-run.  ``--apply`` is the only way to mutate the registry.
No metric is inferred from a note or copied from the old ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from core.engine import CostModel
from engine.metrics import metrics as compute_metrics
from governance.holdout import assert_search_clean, boundary


@dataclass(frozen=True)
class Target:
    family: str
    version: str
    start: str


@dataclass(frozen=True)
class RunGroup:
    runner: str
    config: dict
    targets: tuple[Target, ...]


# There are four unique executions and six registry windows.  The 2023 windows
# are slices of the matching full-history execution, avoiding redundant reads
# without changing any signal or metric.
RUN_GROUPS = (
    RunGroup(
        runner="hq_momentum",
        config={"version": "v1.0-full", "start": "2012-01-01"},
        targets=(
            Target("hq-momentum-hedged", "v1.0-full", "2012-01-01"),
            Target("hq-momentum-hedged", "v1.0", "2023-01-01"),
        ),
    ),
    RunGroup(
        runner="large_cap",
        config={
            "version": "v1.0-full",
            "start": "2010-01-01",
            "buffer_size": 0.02,
            "w_cpv_max": 0.0,
        },
        targets=(
            Target("large-cap-growth-hedged", "v1.0-full", "2010-01-01"),
        ),
    ),
    RunGroup(
        runner="large_cap",
        config={
            "version": "v1.0",
            "start": "2023-01-01",
            "buffer_size": 0.01,
            "w_cpv_max": 0.0,
        },
        targets=(
            Target("large-cap-growth-hedged", "v1.0", "2023-01-01"),
        ),
    ),
    RunGroup(
        runner="large_cap",
        config={
            "version": "v1.1-full",
            "start": "2012-01-01",
            "buffer_size": 0.01,
            "w_cpv_max": 0.5,
        },
        targets=(
            Target("large-cap-growth-hedged", "v1.1-full", "2012-01-01"),
            Target("large-cap-growth-hedged", "v1.1", "2023-01-01"),
        ),
    ),
)

EXPECTED_TARGETS = {
    (target.family, target.version)
    for group in RUN_GROUPS
    for target in group.targets
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _series_digest(series: pd.Series) -> str:
    """Hash exact dates and IEEE-754 values, independent of CSV formatting."""
    digest = hashlib.sha256()
    for date, value in series.items():
        digest.update(str(pd.Timestamp(date).value).encode("ascii"))
        digest.update(b"\0")
        digest.update(float(value).hex().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _source_hashes(runner: str) -> dict[str, str]:
    paths = (
        ROOT / "core/engine.py",
        ROOT / "core/hedged_portfolio.py",
        ROOT / f"strategies/{runner}.py",
        Path(__file__).resolve(),
    )
    return {str(path.relative_to(ROOT)): _sha256_file(path) for path in paths}


def _data_vintage() -> dict:
    manifest_path = ROOT / "data_lake/_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"canonical data-lake manifest is required for auditable restatement: {manifest_path}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "manifest": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": _sha256_file(manifest_path),
        "fingerprint": (manifest.get("data_vintage") or {}).get("fingerprint"),
        "last_date": (manifest.get("data_vintage") or {}).get("last_date"),
    }


def _default_runner(name: str, config: dict) -> dict:
    if name == "large_cap":
        from strategies.large_cap import StrategyConfig, run_large_cap_strategy

        return run_large_cap_strategy(StrategyConfig(**config))
    if name == "hq_momentum":
        from strategies.hq_momentum import StrategyConfig, run_hq_momentum_strategy

        return run_hq_momentum_strategy(StrategyConfig(**config))
    raise ValueError(f"unknown restatement runner: {name}")


def _registry_records() -> dict[tuple[str, str], dict]:
    import strategy_registry

    records = {}
    for family in strategy_registry._load().get("families", []):
        if family.get("id") not in {"large-cap-growth-hedged", "hq-momentum-hedged"}:
            continue
        for version in family.get("versions", []):
            records[(family["id"], version["version"])] = version
    if set(records) != EXPECTED_TARGETS:
        missing = sorted(EXPECTED_TARGETS - set(records))
        unexpected = sorted(set(records) - EXPECTED_TARGETS)
        raise RuntimeError(
            "hedged-family registry inventory changed; update the explicit repair scope "
            f"before running (missing={missing}, unexpected={unexpected})"
        )
    return records


def _core_metric_payload(returns: pd.Series) -> dict:
    calculated = compute_metrics(returns)
    keys = ("annual", "vol", "sharpe", "maxdd", "calmar", "n")
    return {
        key: int(calculated[key]) if key == "n" else float(calculated[key])
        for key in keys
    }


def build_restatement_plan(
    *,
    runner: Callable[[str, dict], dict] = _default_runner,
    run_at: str | None = None,
) -> list[dict]:
    """Run all corrected strategies and return six fully evidenced mutations."""
    records = _registry_records()
    vault_start = boundary()
    observed_at = run_at or datetime.now(timezone.utc).isoformat()
    canonical_cost = asdict(CostModel())
    vintage = _data_vintage()
    plan = []

    for group in RUN_GROUPS:
        source_hashes = _source_hashes(group.runner)
        source_bundle_digest = hashlib.sha256(
            json.dumps(source_hashes, sort_keys=True).encode("utf-8")
        ).hexdigest()
        result = runner(group.runner, dict(group.config))
        all_returns = pd.Series(result.get("returns"), dtype=float).dropna().sort_index()
        if all_returns.empty:
            raise RuntimeError(f"{group.runner} returned no returns")

        engine_result = result.get("engine_result")
        long_cost = getattr(engine_result, "cost", None)
        if long_cost is None:
            raise RuntimeError(f"{group.runner} did not expose canonical long-leg cost evidence")
        long_cost = pd.Series(long_cost, dtype=float).sort_index()
        if float(long_cost.sum()) <= 0:
            raise RuntimeError(
                f"{group.runner} charged no long-leg transaction cost; refusing restatement"
            )

        for target in group.targets:
            returns = all_returns.loc[
                (all_returns.index >= pd.Timestamp(target.start))
                & (all_returns.index < vault_start)
            ]
            if len(returns) < 100:
                raise RuntimeError(
                    f"{target.family}/{target.version} has only {len(returns)} pre-holdout observations"
                )
            assert_search_clean(
                returns.index,
                label=f"R-COST-001 {target.family}/{target.version}",
            )
            target_cost = long_cost.loc[
                (long_cost.index >= pd.Timestamp(target.start))
                & (long_cost.index < vault_start)
            ]
            return_digest = _series_digest(returns)
            audit_id = (
                f"R-COST-001/{target.family}/{target.version}/"
                f"{return_digest[:12]}-{source_bundle_digest[:12]}"
            )
            audit = {
                "audit_id": audit_id,
                "rule": "R-COST-001 / ADR-032",
                "run_at": observed_at,
                "runner": f"strategies.{group.runner}",
                "runner_config": dict(group.config),
                "sample_start": str(returns.index.min().date()),
                "sample_end": str(returns.index.max().date()),
                "holdout_boundary": str(vault_start.date()),
                "n_observations": int(len(returns)),
                "return_digest": return_digest,
                "version_returns_digest": return_digest,
                "long_leg_cost_total": float(target_cost.sum()),
                "long_leg_cost_digest": _series_digest(target_cost),
                "data_vintage": vintage,
                "source_hashes": source_hashes,
                "source_bundle_digest": source_bundle_digest,
                "nine_gate_recertified": False,
            }

            existing = records[(target.family, target.version)]
            prior = next(
                (
                    row
                    for row in (existing.get("evidence") or {}).get(
                        "execution_cost_restatements", []
                    )
                    if row.get("audit_id") == audit_id
                ),
                None,
            )
            if prior is not None:
                # Preserve the first observed timestamp so repeated --apply is
                # idempotent for the same source/returns evidence.
                audit["run_at"] = prior["run_at"]

            calculated = _core_metric_payload(returns)
            notes = (
                f"R-COST-001 成本重述：{audit['sample_start']}~{audit['sample_end']} "
                f"long 腿按 canonical CostModel(买{canonical_cost['buy_cost']:.3%}/"
                f"卖{canonical_cost['sell_cost']:.3%}/融资{canonical_cost['financing_rate']:.1%})重算；"
                f"年化 {calculated['annual']:.2%}、最大回撤 {calculated['maxdd']:.2%}、"
                f"Sharpe {calculated['sharpe']:.2f}。旧免成本绩效与组合边际叙述作废；"
                "保留原生命周期状态，Nine-Gate 未在本次重述中重新认证。"
            )
            plan.append(
                {
                    "family": target.family,
                    "version": target.version,
                    "metrics": calculated,
                    "cost_model": canonical_cost,
                    "audit": audit,
                    "notes": notes,
                    "already_applied": prior is not None,
                    "returns": returns,
                }
            )

    if {(row["family"], row["version"]) for row in plan} != EXPECTED_TARGETS:
        raise AssertionError("restatement plan did not cover the complete affected inventory")
    return sorted(plan, key=lambda row: (row["family"], row["version"]))


def apply_restatement_plan(
    plan: list[dict], *, returns_root: Path | None = None
) -> list[str]:
    """Apply registry evidence and replace stale hedged return caches canonically."""
    import strategy_registry
    from lake.version_returns import write_version_returns

    applied = []
    for row in plan:
        identity = strategy_registry.restate_execution_costs(
            row["family"],
            row["version"],
            metrics=row["metrics"],
            cost_model=row["cost_model"],
            audit=row["audit"],
            notes=row["notes"],
        )
        write_version_returns(
            row["returns"],
            family=row["family"],
            version=row["version"],
            root=returns_root,
        )
        applied.append(identity)
    return applied


def _json_report(plan: list[dict], *, applied: bool) -> dict:
    return {
        "mode": "apply" if applied else "dry_run",
        "rule": "R-COST-001 / ADR-032",
        "covered": len(plan),
        "expected": len(EXPECTED_TARGETS),
        "mutated_registry": applied,
        "versions": [
            {
                "identity": f"{row['family']}/{row['version']}",
                "already_applied": row["already_applied"],
                "metrics": row["metrics"],
                "audit_id": row["audit"]["audit_id"],
                "sample": [row["audit"]["sample_start"], row["audit"]["sample_end"]],
            }
            for row in plan
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write all six completed restatements through strategy_registry",
    )
    args = parser.parse_args()

    plan = build_restatement_plan()
    if args.apply:
        apply_restatement_plan(plan)
    print(json.dumps(_json_report(plan, applied=args.apply), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
