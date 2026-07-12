"""R-COST-001 guard for formal backtest paths.

Formal strategy/runtime code may not instantiate ``CostModel`` with stock-leg
rates **below** the canonical floors (buy 0.225% / sell 0.275%). Zero and
"optimistic low positive" (e.g. etf 5bp) are both rejected.

Cost sensitivity that **raises** costs above the floor is allowed. Research
scripts under ``scripts/research`` and ``scratch/`` are outside this guard;
production-capable paths are closed by default through ``PROTECTED_ROOTS``.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTECTED_ROOTS = (
    "strategies",
    "portfolio",
    "workflow",
    "factory",
    "services/actions",
    "core/analysis",
)

# Keep in sync with core.engine.CANONICAL_* (literal for the static guard).
MIN_BUY_COST = 0.00225
MIN_SELL_COST = 0.00275


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _literal_number(
    node: ast.AST,
    assignments: dict[str, ast.AST] | None = None,
    seen: set[str] | None = None,
) -> float | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal_number(node.operand, assignments, seen)
        return -value if value is not None else None
    if isinstance(node, ast.Name) and assignments and node.id in assignments:
        seen = set(seen or ())
        if node.id in seen:
            return None
        return _literal_number(assignments[node.id], assignments, seen | {node.id})
    return None


def scan_source(src: str, *, rel: str = "") -> list[str]:
    """Return under-floor stock-cost violations in one Python source."""
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"{rel}: syntax error prevents cost audit: {exc}"]
    assignments: dict[str, ast.AST] = {}
    for candidate in ast.walk(tree):
        if isinstance(candidate, ast.Assign):
            for target in candidate.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = candidate.value
        elif isinstance(candidate, ast.AnnAssign) and isinstance(candidate.target, ast.Name):
            if candidate.value is not None:
                assignments[candidate.target.id] = candidate.value
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node) != "CostModel":
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        values = {
            key: _literal_number(kwargs[key], assignments)
            for key in ("buy_cost", "sell_cost")
            if key in kwargs
        }
        bad: list[str] = []
        buy = values.get("buy_cost")
        sell = values.get("sell_cost")
        if buy is not None and buy < MIN_BUY_COST:
            bad.append(f"buy_cost={buy}<{MIN_BUY_COST}")
        if sell is not None and sell < MIN_SELL_COST:
            bad.append(f"sell_cost={sell}<{MIN_SELL_COST}")
        if bad:
            violations.append(
                f"{rel}:L{node.lineno} CostModel undercuts canonical floor ({', '.join(bad)}); "
                "formal A-share stock legs must use CostModel() / formal_cost_model()"
            )
    return violations


def _protected_files() -> list[Path]:
    files: list[Path] = []
    for root in PROTECTED_ROOTS:
        base = ROOT / root
        if base.is_file():
            files.append(base)
        elif base.exists():
            files.extend(base.rglob("*.py"))
    return sorted(
        p for p in files
        if "__pycache__" not in p.parts and "archive" not in p.parts
    )


def main() -> int:
    violations: list[str] = []
    files = _protected_files()
    for path in files:
        rel = str(path.relative_to(ROOT))
        violations.extend(scan_source(path.read_text(encoding="utf-8"), rel=rel))
    if violations:
        print("R-COST-001 formal-path cost violations:")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print(f"R-COST-001 cost guard passed ({len(files)} formal Python files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
