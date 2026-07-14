"""Holdout 合规守卫——自动选择路径必须把择优数据截到 <boundary(LOOP_ENGINEERING §5.2)。

背景(§5.2 缝③):holdout 边界此前靠各脚本手工加,默认就漏——全仓 80+ 处 load 全样本,
只有少数截断。任何**在自动环里 load 全样本并据此择优/排序/边际定级**的路径,若不截到
<boundary,就是"loop 偷看金库" = 工业化自欺。本守卫使用闭世界发现:已登记路径必须真实
调用 ``assert_search_clean`` / ``validate_on_holdout``，新出现的搜索/晋级入口默认失败，
直到加入 REQUIRED 并说明用途。注释、字符串或字面量死分支不算合规调用。

新增自动选择路径(load 全样本 + 排序/择优/边际定级)时:① 把择优数据截到 <boundary;
② 把文件加进 REQUIRED。纯监控/报表/实盘信号(decay_monitor/tradability/dashboard/
paper_trade/live_readiness)合法使用全/近期数据,**不是选择**,不在此列。
"""
import ast
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 已知的"自动选择路径":load 全样本后据此择优/排序/打分/验证 → 必须 holdout 截断。
REQUIRED = {
    "scripts/ops/scheduled_factor_search.py": "周度因子搜索 + 9-Gate 选择",
    "portfolio/cross_asset.py": "跨资产防御腿 Δsharpe 择优",
    "workflow/promote.py": "_run_marginal 边际 ACTIVE/SHADOW 定级",
    "workflow/phase2_backtest.py": "三段回测/成本/相关性/decay 验证栈(ADR-021)",
    "workflow/phase3_wf.py": "walk-forward 训练/测试窗口(ADR-021)",
    "workflow/promote_composite.py": "组合晋级 9-Gate / 候选持久化证据",
    "workflow/nine_gate_runner.py": "统一 9-Gate 证据生成与持久化",
    "workflow/research_stages.py": "研究工作台 L0-L3 自动定级",
    "services/actions/autoresearch.py": "AutoResearch L0-L3 action 入口",
    "services/actions/autoresearch_search.py": "AutoResearch island/WF action 入口",
    "factory/autoresearch/pipeline.py": "AutoResearch L0-L3 验证 chokepoint",
    "factory/autoresearch/islands.py": "多岛候选搜索与冠军选择 chokepoint",
    "factory/autoresearch/walkforward.py": "元级 walk-forward 冠军选择 chokepoint",
    # factory/lines 自身入口(审计#10):不得只靠调用方截断
    "factory/lines/line2_validation/l0_ic_scan.py": "L0 IC 扫描入口 holdout 自检",
    "factory/lines/line2_validation/l1_quick_bt.py": "L1 快回测入口 holdout 自检",
    "factory/lines/line2_validation/l2_multi_regime.py": "L2 multi-regime 入口 holdout 自检",
    "factory/lines/line2_validation/l3_walk_forward.py": "L3 walk-forward 入口 holdout 自检",
    "factory/lines/line2_validation/holdout_guard.py": "lines 共用 assert_factory_panels_clean",
    "factory/lines/line3_marginal/marginal_eval.py": "边际评分入口 holdout 自检",

    # scripts/research 中仍会产生候选/证据的活入口。这些不能因为位于
    # “研究脚本”目录就逃过金库纪律。
    "scripts/research/fundamental_factor_screen.py": "基本面因子扫描与金库验真",
    "scripts/research/historical_memory_rankic_experiment.py": "历史记忆 RankIC 候选实验",
    "scripts/research/run_alphas_evolution_search.py": "Alpha101 进化搜索",
    "scripts/research/value_rescue.py": "value 构造扫描与金库验真",
}

# REQUIRED 不再是“文件里某处有一次 guard 就算过”。每个路径绑定到具体
# 入口；入口本体或它静态可达的同模块 helper 必须执行 holdout 调用。
# 列出多个入口时，每一个都必须合规。类方法用 ``Class.method``。
REQUIRED_ENTRYPOINTS = {
    "scripts/ops/scheduled_factor_search.py": ("main",),
    "portfolio/cross_asset.py": ("search_cross_asset_legs",),
    "workflow/promote.py": ("promote_spec", "promote_hypothesis", "promote_pool_l3"),
    "workflow/phase2_backtest.py": ("Phase2Runner.run",),
    "workflow/phase3_wf.py": ("WF3Runner.run",),
    "workflow/promote_composite.py": ("run_pipeline",),
    "workflow/nine_gate_runner.py": ("run_evaluation",),
    "workflow/research_stages.py": (
        "load_stage_data", "run_hypothesis_stage", "run_autoresearch_stage",
    ),
    "services/actions/autoresearch.py": ("_run_candidates", "run_autoresearch_seeds"),
    "services/actions/autoresearch_search.py": (
        "run_autoresearch_island_search", "run_autoresearch_walk_forward",
    ),
    "factory/autoresearch/pipeline.py": ("run_validation_pipeline",),
    "factory/autoresearch/islands.py": ("run_island_search",),
    "factory/autoresearch/walkforward.py": ("run_walk_forward_search",),
    "factory/lines/line2_validation/l0_ic_scan.py": (
        "precompute_forward_returns", "run_l0",
    ),
    "factory/lines/line2_validation/l1_quick_bt.py": ("run_l1",),
    "factory/lines/line2_validation/l2_multi_regime.py": ("run_l2",),
    "factory/lines/line2_validation/l3_walk_forward.py": ("run_l3",),
    "factory/lines/line2_validation/holdout_guard.py": ("assert_factory_panels_clean",),
    "factory/lines/line3_marginal/marginal_eval.py": (
        "run_candidate_returns", "evaluate_candidate",
    ),
    "scripts/research/fundamental_factor_screen.py": ("main", "screen"),
    "scripts/research/historical_memory_rankic_experiment.py": ("run",),
    "scripts/research/run_alphas_evolution_search.py": ("main",),
    "scripts/research/value_rescue.py": ("main", "screen"),
}
HOLDOUT_CALLS = {"assert_search_clean", "validate_on_holdout", "assert_factory_panels_clean"}
# Backward-compatible inspection helper for tests and callers.  Enforcement in
# main() deliberately uses has_holdout_call() so comments/strings cannot pass.
BOUND = re.compile(
    r"boundary\(|assert_search_clean|validate_on_holdout|assert_factory_panels_clean"
)
SELECTION_DEFINITIONS = {
    "run_validation_pipeline",
    "run_island_search",
    "run_walk_forward_search",
    "run_autoresearch_island_search",
    "run_autoresearch_walk_forward",
    "run_evaluation",
    "promote_spec",
    "promote_hypothesis",
    "promote_pool_l3",
    "promote_composite",
    "load_stage_data",
    "_load_validation_data",
    "run_l0",
    "run_l1",
    "run_l2",
    "run_l3",
    "evaluate_candidate",
    "run_candidate_returns",
    "precompute_forward_returns",
}
DISCOVERY_ROOTS = (
    "workflow",
    "factory/autoresearch",
    "factory/lines",
    "services/actions",
    "scripts/ops",
    "scripts/research",
    "portfolio",
    "apps",
)
DELEGATED = {
    "scripts/ops/bulk_promote.py": {
        "reason": "approval wrapper; all scoring runs through guarded workflow promotion",
        # Kept for callers that inspected the original DELEGATED schema.
        "calls": {"promote_approved_candidate", "promote_pool_l3"},
        "entrypoints": {
            "run_bulk_promotion": {"promote_approved_candidate", "promote_pool_l3"},
        },
    },
    "apps/factory_cli.py": {
        "reason": "CLI adapters delegate scoring/promotion to guarded factory/workflow entrypoints",
        "entrypoints": {
            "cmd_run_l0": {"run_l0"},
            "cmd_run_l1": {"run_l1"},
            "cmd_run_l2": {"run_l2"},
            "cmd_run_l3": {"run_l3"},
            "cmd_run_marginal": {"evaluate_candidate"},
            "cmd_promote": {"promote_pool_l3"},
        },
    },
    "scripts/research/alpha_audit_fund_mom.py": {
        "reason": "fixed-factor audit loads only through guarded validation-data adapter",
        "entrypoints": {"main": {"_load_validation_data"}},
    },
    "scripts/research/audit_all_factors.py": {
        "reason": "module audit loads only through guarded validation-data adapter",
        "entrypoints": {"<module>": {"_load_validation_data"}},
    },
    "scripts/research/autoresearch_closed_loop.py": {
        "reason": "closed-loop experiment delegates loading and search to guarded actions",
        "entrypoints": {
            "main": {"_load_validation_data", "run_autoresearch_walk_forward"},
        },
    },
    "scripts/research/marginal_fitness_ab.py": {
        "reason": "A/B search delegates to the guarded AutoResearch action",
        "entrypoints": {
            "main": {"_load_validation_data", "run_autoresearch_island_search"},
        },
    },
    "scripts/research/promote_fundamental_momentum.py": {
        "reason": "promotion wrapper delegates to guarded workflow.promote_spec",
        "entrypoints": {"main": {"promote_spec"}},
    },
    "scripts/research/run_alternative_factors_search.py": {
        "reason": "search-space wrapper delegates to guarded AutoResearch island action",
        "entrypoints": {"main": {"run_autoresearch_island_search"}},
    },
    "scripts/research/run_nine_gates_all.py": {
        "reason": "compatibility wrapper delegates to guarded canonical Nine-Gate runner",
        "entrypoints": {"main": {"run_evaluation"}},
    },
    "scripts/research/style_neutralization.py": {
        "reason": "fixed-factor audit loads only through guarded validation-data adapter",
        "entrypoints": {"main": {"_load_validation_data"}},
    },
    "scripts/research/turnover_ab_l1_net.py": {
        "reason": "A/B validation delegates to guarded loader and L0-L3 pipeline",
        "entrypoints": {"main": {"_load_validation_data", "run_validation_pipeline"}},
    },
    "scripts/research/turnover_fitness_ab.py": {
        "reason": "A/B search delegates to the guarded AutoResearch action",
        "entrypoints": {
            "main": {"_load_validation_data", "run_autoresearch_island_search"},
        },
    },
}

# 精确路径例外：只允许不产生候选、不写 registry/review queue 的手工诊断。
# 例外不是 glob；新文件仍会 fail closed。
EXEMPT = {
    "scripts/research/toc_right_tail_experiment.py": (
        "pre-registered fixed-arm mechanism falsification; report-only"
    ),
}

_SELECTION_WORDS = (
    "search", "promote", "promotion", "champion", "select", "selection",
    "optimize", "optimization", "rank", "ranking", "score", "scoring",
)
_DATA_CALLS = {
    "load_prices", "load_price_panels", "load_panel", "load_raw_close",
    "read_parquet", "read_csv", "read_feather",
}


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _parse_source(src: str) -> ast.AST | None:
    try:
        return ast.parse(src)
    except SyntaxError:
        return None


def _literal_branch(test: ast.expr) -> bool | None:
    """Return a literal branch value, or None when runtime-dependent."""
    if isinstance(test, ast.Constant):
        return bool(test.value)
    return None


class _ExecutableCallVisitor(ast.NodeVisitor):
    """Calls in one executable body, excluding nested definitions and dead branches."""

    def __init__(self) -> None:
        self.calls: set[str] = set()
        self.local_calls: set[str] = set()

    def visit_Call(self, node: ast.Call):  # noqa: N802 - ast visitor API
        self.calls.add(_call_name(node))
        if isinstance(node.func, ast.Name):
            self.local_calls.add(node.func.id)
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"self", "cls"}
        ):
            # A same-class helper may be reached through self/cls.  Do not
            # follow arbitrary ``obj.helper()`` calls merely because an unused
            # local function happens to share that name.
            self.local_calls.add(node.func.attr)
        self.generic_visit(node)

    def visit_block(self, body: list[ast.stmt]) -> bool:
        """Visit a statement block; return whether control can reach its end."""
        for statement in body:
            falls_through = self.visit(statement)
            if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                return False
            if falls_through is False:
                return False
        return True

    def visit_FunctionDef(self, node: ast.FunctionDef):  # noqa: N802
        return  # a nested helper is not executed merely because it is defined

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):  # noqa: N802
        return

    def visit_ClassDef(self, node: ast.ClassDef):  # noqa: N802
        return

    def visit_Lambda(self, node: ast.Lambda):  # noqa: N802
        return

    def visit_If(self, node: ast.If):  # noqa: N802 - ast visitor API
        literal = _literal_branch(node.test)
        if literal is not None:
            return self.visit_block(node.body if literal else node.orelse)
        self.visit(node.test)
        body_falls = self.visit_block(node.body)
        else_falls = self.visit_block(node.orelse) if node.orelse else True
        return body_falls or else_falls

    def visit_IfExp(self, node: ast.IfExp):  # noqa: N802 - ast visitor API
        literal = _literal_branch(node.test)
        if literal is not None:
            self.visit(node.body if literal else node.orelse)
            return
        self.generic_visit(node)

    def visit_While(self, node: ast.While):  # noqa: N802 - ast visitor API
        literal = _literal_branch(node.test)
        if literal is False:
            return self.visit_block(node.orelse)
        self.visit(node.test)
        self.visit_block(node.body)
        self.visit_block(node.orelse)
        return True  # conservatively assume a non-literal loop can terminate

    def visit_BoolOp(self, node: ast.BoolOp):  # noqa: N802 - ast visitor API
        for value in node.values:
            self.visit(value)
            if not isinstance(value, ast.Constant):
                continue
            truth = bool(value.value)
            if isinstance(node.op, ast.And) and not truth:
                break
            if isinstance(node.op, ast.Or) and truth:
                break


def _body_calls(body: list[ast.stmt]) -> set[str]:
    visitor = _ExecutableCallVisitor()
    visitor.visit_block(body)
    return visitor.calls


def _body_local_calls(body: list[ast.stmt]) -> set[str]:
    visitor = _ExecutableCallVisitor()
    visitor.visit_block(body)
    return visitor.local_calls


def _function_nodes(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Index module functions, methods and nested helpers by qualified name."""
    found: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def collect(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = f"{prefix}.{node.name}" if prefix else node.name
                found[qualified] = node
                collect(node.body, qualified)
            elif isinstance(node, ast.ClassDef):
                qualified = f"{prefix}.{node.name}" if prefix else node.name
                collect(node.body, qualified)
            elif isinstance(node, ast.If):
                literal = _literal_branch(node.test)
                if literal is not None:
                    collect(node.body if literal else node.orelse, prefix)
                else:
                    collect(node.body, prefix)
                    collect(node.orelse, prefix)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)):
                # Definitions in runtime-dependent blocks are still local symbols.  Their
                # *calls* are filtered separately by _ExecutableCallVisitor.
                for field in ("body", "orelse", "finalbody"):
                    collect(getattr(node, field, []), prefix)
                for handler in getattr(node, "handlers", []):
                    collect(handler.body, prefix)

    collect(getattr(tree, "body", []))
    return found


def _entrypoint_calls(tree: ast.AST, entrypoint: str) -> set[str] | None:
    """Return all calls reachable through same-module helpers from one entrypoint."""
    functions = _function_nodes(tree)
    simple: dict[str, list[str]] = {}
    for qualified, node in functions.items():
        simple.setdefault(node.name, []).append(qualified)

    if entrypoint == "<module>":
        initial = _body_calls(getattr(tree, "body", []))
        pending_names = list(_body_local_calls(getattr(tree, "body", [])))
        all_calls = set(initial)
        visited: set[str] = {"<module>"}
    else:
        if entrypoint not in functions:
            return None
        pending_names = []
        all_calls = set()
        visited = set()

        def enqueue(qualified: str) -> None:
            if qualified in visited:
                return
            visited.add(qualified)
            calls = _body_calls(functions[qualified].body)
            all_calls.update(calls)
            pending_names.extend(_body_local_calls(functions[qualified].body))

        enqueue(entrypoint)

    while pending_names:
        name = pending_names.pop()
        local = simple.get(name, [])
        # Ambiguous simple names are not followed: guessing which helper is called would
        # turn the fail-closed guard into a false-pass mechanism.
        if len(local) != 1:
            continue
        qualified = local[0]
        if qualified in visited:
            continue
        visited.add(qualified)
        calls = _body_calls(functions[qualified].body)
        all_calls.update(calls)
        pending_names.extend(_body_local_calls(functions[qualified].body))
    return all_calls


def missing_holdout_entrypoints(src: str, entrypoints) -> tuple[str, ...]:
    """Return named entrypoints with no reachable active holdout call."""
    tree = _parse_source(src)
    if tree is None:
        return tuple(entrypoints)
    missing = []
    for entrypoint in entrypoints:
        calls = _entrypoint_calls(tree, entrypoint)
        if calls is None or not calls.intersection(HOLDOUT_CALLS):
            missing.append(entrypoint)
    return tuple(missing)


def has_holdout_call(src: str, entrypoints=None) -> bool:
    """Only potentially executable holdout calls count.

    With ``entrypoints`` supplied, every named entrypoint must reach a guard through
    its own active body or a same-module helper it actually calls.  The one-argument
    form is retained for compatibility and answers only whether the module contains
    any potentially executable holdout call.
    """
    if entrypoints is not None:
        bound = (entrypoints,) if isinstance(entrypoints, str) else tuple(entrypoints)
        return not missing_holdout_entrypoints(src, bound)
    tree = _parse_source(src)
    if tree is None:
        return False
    calls = _body_calls(getattr(tree, "body", []))
    for node in _function_nodes(tree).values():
        calls.update(_body_calls(node.body))
    return bool(calls.intersection(HOLDOUT_CALLS))


def _selection_name(name: str) -> bool:
    """Match selection words as identifiers, not substrings like reSEARCH/zSCORE."""
    tokens = tuple(token for token in re.split(r"[^a-z0-9]+", name.lower()) if token)
    return any(token in _SELECTION_WORDS for token in tokens)


def is_selection_source(src: str) -> bool:
    """Conservatively identify automatic selection entrypoints."""
    tree = _parse_source(src)
    if tree is None:
        return False
    defs = {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if defs & SELECTION_DEFINITIONS:
        return True
    calls = {_call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    if calls & SELECTION_DEFINITIONS:
        return True
    named_selection = any(_selection_name(name) for name in defs)
    # Ranking is ubiquitous inside a fixed strategy/backtest; by itself ``nlargest``
    # must not reclassify every portfolio constructor as model selection.  Bind the
    # operation to an explicitly selection-named definition (e.g. rank_candidates,
    # search_*, promote_*).  ``rank_candidates + read_parquet + nlargest`` is thereby
    # caught, while a plain fixed-strategy weight builder is not.
    return named_selection and bool(calls & _DATA_CALLS)


def discover_selection_paths() -> set[str]:
    """Discover selection sources tracked in Git's index under governed roots.

    Shared worktrees often contain another session's untracked probes.  Treating those
    as repository policy would make the same commit pass in a clean checkout but fail
    locally.  ``git ls-files --cached`` covers committed files and staged additions;
    when Git metadata is unavailable (e.g. a source archive), fall back to filesystem
    traversal so the guard remains usable rather than silently discovering nothing.
    """
    indexed: set[Path] | None = None
    try:
        subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"],
            check=True, capture_output=True, text=True,
        )
        listed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--cached", "--", "*.py"],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        indexed = set()
        for rel in listed:
            # `git -C ROOT ls-files` emits paths relative to ROOT, even when the
            # repository top-level is a parent directory.
            path = (ROOT / rel).resolve()
            try:
                path.relative_to(ROOT)
            except ValueError:
                continue
            if path.exists():
                indexed.add(path)
    except (OSError, subprocess.CalledProcessError):
        indexed = None

    discovered = set()
    for rel_root in DISCOVERY_ROOTS:
        base = ROOT / rel_root
        if not base.exists():
            continue
        candidates = base.rglob("*.py") if indexed is None else (
            path for path in indexed if path.is_relative_to(base)
        )
        for path in candidates:
            if "__pycache__" in path.parts or "archive" in path.parts:
                continue
            if is_selection_source(path.read_text(encoding="utf-8")):
                discovered.add(str(path.relative_to(ROOT)))
    return discovered


def _called_names(src: str) -> set[str]:
    tree = _parse_source(src)
    if tree is None:
        return set()
    return {_call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}


def missing_delegated_entrypoints(src: str, policy: dict) -> tuple[str, ...]:
    """Validate that every delegated entrypoint reaches its registered chokepoint."""
    tree = _parse_source(src)
    if tree is None:
        return tuple(policy.get("entrypoints", {}))
    missing = []
    for entrypoint, guarded_calls in policy.get("entrypoints", {}).items():
        calls = _entrypoint_calls(tree, entrypoint)
        if calls is None or not set(guarded_calls).issubset(calls):
            missing.append(entrypoint)
    return tuple(missing)

# ── P0-B(ADR-021):锁定 holdout.start 配置值 ──
# boundary 是软配置(settings.yaml::holdout.start),改它 = 改金库范围:原受保护的金库段
# 突然变「可搜索」,所有基于旧 boundary 的 validate_on_holdout 记录失去唯一性意义。
# 此处把当前值的 hash 钉死;任何改动让守卫 exit 1,强制走 DECISIONS(ADR)+ 更新本 pin。
SETTINGS_YAML = ROOT / "app_config" / "settings.yaml"
EXPECTED_BOUNDARY = "2025-01-01"
EXPECTED_BOUNDARY_HASH = "14973c591b26d5116b3ce3508c60adfe345a1201723a45f18dacc0293da2ec7a"


def check_boundary_lock() -> list[tuple[str, str]]:
    """holdout.start 必须 == 钉死值,否则违规(改金库须 ADR + 更新本 pin)。"""
    try:
        import yaml
        cfg = yaml.safe_load(SETTINGS_YAML.read_text(encoding="utf-8")) or {}
        start = str((cfg.get("holdout") or {}).get("start", ""))
    except Exception as exc:  # noqa: BLE001 — 读不到配置即视为违规,不静默
        return [("app_config/settings.yaml", f"无法读取 holdout.start: {exc}")]
    h = hashlib.sha256(start.encode()).hexdigest()
    if h != EXPECTED_BOUNDARY_HASH:
        return [(
            "app_config/settings.yaml::holdout.start",
            f"金库边界被改动:当前 {start!r}(hash {h[:12]})≠ 钉死 {EXPECTED_BOUNDARY!r}"
            f"(hash {EXPECTED_BOUNDARY_HASH[:12]})。改金库 = 改唯一性语义,须先记 DECISIONS(ADR)"
            f"并同步更新 check_holdout_compliance.py 的 EXPECTED_BOUNDARY[_HASH]。",
        )]
    return []


def check_boundary_monotonic() -> list[tuple[str, str]]:
    """ADR-023:强制 boundary 只进不退,且 settings.holdout.start == 历史账本最大值。

    边界历史账本(app_config/holdout_boundary_history.jsonl,git 跟踪)是 active 金库的权威:
      ① 账本必须存在且非空(genesis 基线);
      ② 严格递增(任一条 <= 前一条 = 后退/重复 = 复活已偷看金库 → 违规);
      ③ settings.holdout.start 必须 == 账本最大值——手改前进(未经 migrate 记录)或后退都判违规。
    推进金库的唯一合法路径 = governance.holdout.migrate_holdout_boundary()。
    """
    import json
    from datetime import date as _date
    hist_path = ROOT / "app_config" / "holdout_boundary_history.jsonl"
    if not hist_path.exists():
        return [("app_config/holdout_boundary_history.jsonl",
                 "边界历史账本缺失:需 genesis 基线(ADR-023 强制)。")]
    hist = []
    for line in hist_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                hist.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    if not hist:
        return [("app_config/holdout_boundary_history.jsonl",
                 "边界历史账本为空:需 genesis 基线(ADR-023 强制)。")]
    try:
        bs = [_date.fromisoformat(str(h["boundary"])) for h in hist]
    except Exception as exc:  # noqa: BLE001
        return [("app_config/holdout_boundary_history.jsonl", f"账本解析失败: {exc}")]
    out = []
    for prev, cur in zip(bs, bs[1:]):
        if cur <= prev:
            out.append(("app_config/holdout_boundary_history.jsonl",
                        f"边界非严格递增:{cur} <= {prev} —— 后退/重复 = 复活已偷看金库(只进不退)。"))
    try:
        import yaml
        cfg = yaml.safe_load(SETTINGS_YAML.read_text(encoding="utf-8")) or {}
        settings_b = _date.fromisoformat(str((cfg.get("holdout") or {}).get("start", "")))
    except Exception as exc:  # noqa: BLE001
        return out + [("app_config/settings.yaml", f"无法读取/解析 holdout.start: {exc}")]
    active = max(bs)
    if settings_b != active:
        out.append((
            "app_config/settings.yaml::holdout.start",
            f"settings.holdout.start={settings_b} ≠ 历史账本 active={active}。"
            f"推进金库须经 migrate_holdout_boundary()(记账+作废旧金库)后再同步 settings+pin;"
            f"后退则被只进不退禁止。",
        ))
    return out


def main() -> int:
    violations = []
    violations.extend(check_boundary_lock())  # P0-B:金库边界配置锁
    violations.extend(check_boundary_monotonic())  # ADR-023:边界只进不退 + 账本一致
    if set(REQUIRED) != set(REQUIRED_ENTRYPOINTS):
        missing_policy = sorted(set(REQUIRED) - set(REQUIRED_ENTRYPOINTS))
        stale_policy = sorted(set(REQUIRED_ENTRYPOINTS) - set(REQUIRED))
        violations.append((
            "scripts/ci/check_holdout_compliance.py::REQUIRED_ENTRYPOINTS",
            f"入口绑定与 REQUIRED 不一致:missing={missing_policy}, stale={stale_policy}",
        ))
    discovered = discover_selection_paths()
    classified = set(REQUIRED) | set(DELEGATED) | set(EXEMPT)
    for rel in sorted(discovered - classified):
        violations.append((
            rel,
            "闭世界发现新的自动搜索/晋级路径:须精确加入 REQUIRED/DELEGATED/EXEMPT 并说明用途",
        ))
    for rel, policy in DELEGATED.items():
        path = ROOT / rel
        if not path.exists():
            violations.append((rel, "DELEGATED 名单中的包装器不存在"))
            continue
        missing = missing_delegated_entrypoints(path.read_text(encoding="utf-8"), policy)
        if missing:
            violations.append((
                rel,
                f"holdout 委托失效:入口 {list(missing)} 未调用其登记的 guarded chokepoint",
            ))
    for rel, why in REQUIRED.items():
        p = ROOT / rel
        if not p.exists():
            violations.append((rel, "文件不存在(REQUIRED 名单过期?)"))
            continue
        entrypoints = REQUIRED_ENTRYPOINTS.get(rel, ())
        missing = missing_holdout_entrypoints(p.read_text(encoding="utf-8"), entrypoints)
        if missing:
            violations.append((
                rel,
                f"自动选择路径({why})入口 {list(missing)} 未执行可达 holdout 自查"
                " → §5.2 缝③ 泄露",
            ))
    scheduled = (ROOT / "scripts/ops/scheduled_factor_search.py").read_text(encoding="utf-8")
    if "review_queue.all()" in scheduled:
        violations.append((
            "scripts/ops/scheduled_factor_search.py",
            "自动审计不得遍历 ReviewQueue.all();只能处理本轮新增 pending",
        ))
    for path in ROOT.rglob("*.py"):
        if any(part in {"data_lake", "scratch", "__pycache__"} for part in path.parts):
            continue
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "validate_on_holdout(" not in text or path.name in {"holdout.py", "check_holdout_compliance.py"}:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            if name != "validate_on_holdout":
                continue
            keywords = {kw.arg for kw in node.keywords}
            if "spec_hash" not in keywords or "data_fingerprint" not in keywords:
                violations.append((
                    str(path.relative_to(ROOT)),
                    "validate_on_holdout 调用缺 spec_hash/data_fingerprint 身份",
                ))
                break
    if violations:
        print("🚨 Holdout 合规违规(自动选择路径必须截到 <boundary,见 LOOP_ENGINEERING §5.2):")
        for rel, msg in violations:
            print(f"  - {rel}: {msg}")
        return 1
    print(
        f"Holdout 合规检查通过({len(REQUIRED)} 个登记路径;"
        f"{len(DELEGATED)} 个显式委托;{len(EXEMPT)} 个精确诊断例外;"
        f"闭世界发现 {len(discovered)} 个选择入口)。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
