"""Pareto front helpers."""
from factory.objectives import pareto_front, scalar_rank


def annotate_pareto(rows):
    front_ids = {(r["family"], r["version"]) for r in pareto_front(rows)}
    out = []
    for row in rows:
        copied = dict(row)
        copied["pareto"] = (row["family"], row["version"]) in front_ids
        copied["rank_score"] = scalar_rank(row)
        out.append(copied)
    return sorted(out, key=lambda r: (not r["pareto"], -r["rank_score"]))
