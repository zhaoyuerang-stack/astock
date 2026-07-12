"""Holdout 合规守卫——自动选择路径必须把择优数据截到 <boundary(LOOP_ENGINEERING §5.2)。

背景(§5.2 缝③):holdout 边界此前靠各脚本手工加,默认就漏——全仓 80+ 处 load 全样本,
只有少数截断。任何**在自动环里 load 全样本并据此择优/排序/边际定级**的路径,若不截到
<boundary,就是"loop 偷看金库" = 工业化自欺。本守卫使用闭世界发现:已登记路径必须真实
调用 ``assert_search_clean`` / ``validate_on_holdout``，新出现的搜索/晋级入口默认失败，
直到加入 REQUIRED 并说明用途。注释或死字符串不算合规调用。

新增自动选择路径(load 全样本 + 排序/择优/边际定级)时:① 把择优数据截到 <boundary;
② 把文件加进 REQUIRED。纯监控/报表/实盘信号(decay_monitor/tradability/dashboard/
paper_trade/live_readiness)合法使用全/近期数据,**不是选择**,不在此列。
"""
import ast
import hashlib
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
}
HOLDOUT_CALLS = {"assert_search_clean", "validate_on_holdout", "assert_factory_panels_clean"}
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
    "portfolio",
)
# Explicit delegation registry.  These wrappers never load/score market data;
# they may only invoke listed REQUIRED chokepoints.  New wrappers fail until a
# reason and allowed calls are reviewed here.
DELEGATED = {
    "scripts/ops/bulk_promote.py": {
        "reason": "approval wrapper; all scoring runs through guarded workflow promotion",
        "calls": {"promote_approved_candidate", "promote_pool_l3"},
    },
}
_SELECTION_WORDS = ("search", "promot", "champion", "select_best", "optim")
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


def has_holdout_call(src: str) -> bool:
    """Only potentially executable calls count; comments and literal-dead branches do not."""
    tree = _parse_source(src)
    if tree is None:
        return False

    class ReachableCallVisitor(ast.NodeVisitor):
        found = False

        def visit_Call(self, node: ast.Call):  # noqa: N802 - ast visitor API
            if _call_name(node) in HOLDOUT_CALLS:
                self.found = True
            self.generic_visit(node)

        def visit_If(self, node: ast.If):  # noqa: N802 - ast visitor API
            if isinstance(node.test, ast.Constant):
                branch = node.body if bool(node.test.value) else node.orelse
                for child in branch:
                    self.visit(child)
                return
            self.generic_visit(node)

        def visit_While(self, node: ast.While):  # noqa: N802 - ast visitor API
            if isinstance(node.test, ast.Constant) and not bool(node.test.value):
                for child in node.orelse:
                    self.visit(child)
                return
            self.generic_visit(node)

    visitor = ReachableCallVisitor()
    visitor.visit(tree)
    return visitor.found


def is_selection_source(src: str) -> bool:
    """Conservative discovery for a new automatic selection entrypoint."""
    tree = _parse_source(src)
    if tree is None:
        return False
    defs = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if defs & SELECTION_DEFINITIONS:
        return True
    calls = {
        _call_name(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    if calls & SELECTION_DEFINITIONS:
        return True
    has_named_selection = any(any(word in name.lower() for word in _SELECTION_WORDS) for name in defs)
    return has_named_selection and bool(calls & _DATA_CALLS)


def discover_selection_paths() -> set[str]:
    discovered: set[str] = set()
    for rel_root in DISCOVERY_ROOTS:
        base = ROOT / rel_root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts or "archive" in path.parts:
                continue
            src = path.read_text(encoding="utf-8")
            if is_selection_source(src):
                discovered.add(str(path.relative_to(ROOT)))
    return discovered


def _called_names(src: str) -> set[str]:
    tree = _parse_source(src)
    if tree is None:
        return set()
    return {
        _call_name(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }

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
    discovered = discover_selection_paths()
    for rel in sorted(discovered - set(REQUIRED) - set(DELEGATED)):
        violations.append((
            rel,
            "闭世界发现新的自动搜索/晋级路径:须加入 REQUIRED、说明用途并调用 assert_search_clean",
        ))
    for rel, policy in DELEGATED.items():
        path = ROOT / rel
        if not path.exists():
            violations.append((rel, "DELEGATED 名单中的包装器不存在"))
            continue
        called = _called_names(path.read_text(encoding="utf-8"))
        if not called.intersection(policy["calls"]):
            violations.append((
                rel,
                f"holdout 委托失效:未调用登记的 guarded chokepoint {sorted(policy['calls'])}",
            ))
    for rel, why in REQUIRED.items():
        p = ROOT / rel
        if not p.exists():
            violations.append((rel, "文件不存在(REQUIRED 名单过期?)"))
            continue
        if not has_holdout_call(p.read_text(encoding="utf-8")):
            violations.append((rel, f"自动选择路径({why})未执行 holdout 自查 → §5.2 缝③ 泄露"))
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
        f"{len(DELEGATED)} 个显式委托;闭世界发现 {len(discovered)} 个选择入口)。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
