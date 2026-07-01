"""分层依赖检查 — 防止跨层倒灌import。

用法:
    python3 scripts/ci/check_layer_deps.py

纯静态AST分析,不执行代码。规则定义见 FORBIDDEN_EDGES:
(source前缀, [禁止依赖的target前缀, ...])

例如 strategies.* 不允许 import factory.* / scripts.research.* / workflow.*,
因为生产组合构建层不应依赖探索层的实现细节。
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 不参与分层检查的目录(测试/脚本工具自身)
EXCLUDE_DIRS = {"__pycache__", ".git", "data_lake", "signals", "reports", "logs", "scratch"}

FORBIDDEN_EDGES = [
    ("run_daily", ["factory.", "scripts.research.", "workflow.", "knowledge.", "api.", "services."]),
    ("strategies.", ["factory.", "scripts.research.", "workflow.", "knowledge.", "api.", "services."]),
    ("factors.", ["factory.", "strategies.", "scripts.research.", "workflow.", "core.", "knowledge.", "api.", "services."]),
    ("lake.", ["factors.", "strategies.", "core.", "factory.", "scripts.research.", "knowledge.", "api.", "services."]),
    ("core.engine", ["factory.", "strategies.", "scripts.research.", "workflow.", "knowledge.", "api.", "services."]),
    ("core.analysis", ["factory.", "strategies.", "scripts.research.", "workflow.", "knowledge.", "api.", "services."]),
    # engine/ 是 core.engine 的底层引擎叶子(metrics/composer/portfolio/factor_analysis),
    # 必须停在最底层:不得反向依赖 factors(状态/因子层)、组合构建层(strategies)或探索层
    # (factory/scripts.research/workflow)。黑名单原先漏了这个与 core/ 平级的顶层目录,
    # 导致 regime.py/strategy_composer.py 倒灌未被发现;两者已迁出至 factory/。
    ("engine.", ["factors.", "factory.", "strategies.", "scripts.research.", "workflow."]),
    ("scripts.data.", ["factory.", "strategies.", "scripts.research.", "workflow.", "knowledge.", "api.", "services."]),
    # ops 默认按生产运维入口处理:不得随手倒灌研究/服务/台账层。
    # 少数已审定的研究编排脚本在 ALLOWED_IMPORT_EXCEPTIONS 中放行;新增例外必须显式留痕。
    ("scripts.ops.", ["factory.", "workflow.", "scripts.research.", "services.", "research_ledger.",
                      "strategy_registry.", "knowledge.", "api.", "metasearch."]),
    # knowledge 是纯机制:只依赖 stdlib(+ duck-typed Hypothesis),不得依赖任何业务层
    ("knowledge.", ["core.", "lake.", "factors.", "strategies.", "factory.", "workflow.", "scripts.", "api.", "services."]),
    # 产品接缝(Phase 0):api 是薄 HTTP 层,只能走 services/contracts,不得直碰引擎
    ("api.", ["core.", "lake.", "factors.", "strategies.", "factory.", "workflow.",
              "engine.", "metasearch.", "knowledge.", "scripts."]),
    # services 是受控接缝(有意允许 import 引擎),但不得反向依赖 api。
    # read 是只读查询面,不得调用 actions 写入/执行面;actions 可按需读 read 视图。
    ("services.read.", ["services.actions."]),
    ("services.", ["api."]),
    # workflow 是可复用晋级库层,不得反向依赖 scripts/research CLI。
    ("workflow.", ["scripts.research."]),
    # contracts 是纯 DTO 叶子:只依赖 pydantic + stdlib,不得依赖任何业务层
    ("contracts.", ["core.", "lake.", "factors.", "strategies.", "factory.", "workflow.",
                    "engine.", "metasearch.", "knowledge.", "scripts.", "services.", "api."]),
]

# 全局禁止import的模块(无论从哪一层):已退场的兼容层 / 死接口。
# core.backtest 已于解耦收尾阶段退场(重命名为 _deprecated_backtest.py.bak),
# 唯一回测路径是 core.engine.BacktestEngine;新代码绝不能再 import core.backtest。
GLOBAL_FORBIDDEN_IMPORTS = ["core.backtest"]

# 已知例外:factors/alpha/ 提供了 to_signal()/default_*_builder() 等便利方法,
# 把Factor直接桥接成core.engine可用的Signal/BacktestEngine。这些import全部
# 是函数体内的延迟导入(避免模块级循环依赖),属于有意为之的人体工学API,
# 不在本次解耦范围内重构,先白名单放行并留痕。
ALLOWED_EXCEPTIONS = {
    ("factors/alpha/base.py", 173),
    ("factors/alpha/search.py", 275),
    ("factors/alpha/search.py", 531),
    ("factors/alpha/search.py", 532),
    ("factors/alpha/search.py", 542),
}

# 文件 + import 目标级例外:比行号稳定,但仍要求新增桥接显式登记。
ALLOWED_IMPORT_EXCEPTIONS = {
    # 研究编排脚本:批量晋级/周度搜索需要桥接 factory → workflow。
    ("scripts/ops/bulk_promote.py", "factory.autoresearch"),
    ("scripts/ops/bulk_promote.py", "services.actions.autoresearch"),
    ("scripts/ops/bulk_promote.py", "workflow.promote"),
    ("scripts/ops/scheduled_factor_search.py", "services.actions.autoresearch_search"),
    ("scripts/ops/scheduled_factor_search.py", "factory.autoresearch.repositories"),
    ("scripts/ops/scheduled_factor_search.py", "research_ledger.ledger"),
    ("scripts/ops/scheduled_factor_search.py", "factory.autoresearch.models"),
    ("scripts/ops/scheduled_factor_search.py", "factory.autoresearch.pipeline"),
    ("scripts/ops/scheduled_factor_search.py", "workflow.from_factory"),
    # 生产衰减监控:读在册版本并经 attach_decay_check 写回衰减审计字段。
    ("scripts/ops/decay_monitor.py", "strategy_registry"),
}

RUNTIME_ARTIFACT_ROOTS = {"data_lake", "reports", "signals", "paper"}

API_ARTIFACT_READ_ALLOWLIST = set()


def module_path(py_file: Path) -> str:
    rel = py_file.relative_to(ROOT).with_suffix("")
    parts = rel.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def imported_modules(py_file: Path):
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except (SyntaxError, UnicodeDecodeError):
        return []
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import, not cross-layer by definition
            if node.module:
                mods.append((node.module, node.lineno))
    return mods


# 台账唯一写入口:strategy_versions.json 只能由 strategy_registry.py 写
# (register_family/register → _save)。其余代码须经 register(),不得直写,
# 否则台账历史/可复现性元数据会被绕过。workflow.phase4_register 也是调
# register(),不直写,因此不在此白名单内也不会被误报。
REGISTRY_FILE = "strategy_versions.json"
REGISTRY_WRITER_ALLOWLIST = {"strategy_registry.py"}


def _mentions_registry(node) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and REGISTRY_FILE in n.value:
            return True
    return False


def _mentions_runtime_artifact(node) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            parts = set(Path(n.value).parts)
            if n.value in RUNTIME_ARTIFACT_ROOTS or parts & RUNTIME_ARTIFACT_ROOTS:
                return True
    return False


def registry_write_violations(py_file: Path):
    """检测对 strategy_versions.json 的直接写操作(write_text/write_bytes/open(...,'w'))。"""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except (SyntaxError, UnicodeDecodeError):
        return []
    # 绑定到注册表路径字面量的变量名
    reg_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _mentions_registry(node.value):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    reg_vars.add(tgt.id)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("write_text", "write_bytes"):
                obj = node.func.value
                if (isinstance(obj, ast.Name) and obj.id in reg_vars) or _mentions_registry(obj):
                    hits.append(node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            if node.args:
                first = node.args[0]
                is_reg = (isinstance(first, ast.Name) and first.id in reg_vars) or _mentions_registry(first)
                mode_w = False
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode_w = any(c in str(node.args[1].value) for c in ("w", "a"))
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode_w = mode_w or any(c in str(kw.value.value) for c in ("w", "a"))
                if is_reg and mode_w:
                    hits.append(node.lineno)
    return hits


def api_runtime_artifact_read_violations(py_file: Path):
    """检测 api 层对 data_lake/reports/signals/paper 的直接文件读取。"""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except (SyntaxError, UnicodeDecodeError):
        return []

    hits = []
    artifact_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _mentions_runtime_artifact(node.value):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    artifact_vars.add(tgt.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            obj = node.func.value
            mentions = _mentions_runtime_artifact(obj) or (
                isinstance(obj, ast.Name) and obj.id in artifact_vars
            )
            if mentions and attr in ("read_text", "read_bytes"):
                hits.append(node.lineno)
            if mentions and attr == "open" and _call_opens_for_read(node, mode_arg_index=0):
                hits.append(node.lineno)
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "pd":
                if attr.startswith("read_") and any(_mentions_runtime_artifact(arg) for arg in node.args):
                    hits.append(node.lineno)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            if node.args and (
                _mentions_runtime_artifact(node.args[0])
                or (isinstance(node.args[0], ast.Name) and node.args[0].id in artifact_vars)
            ) and _call_opens_for_read(node, mode_arg_index=1):
                hits.append(node.lineno)
    return hits


def runtime_artifact_write_violations(py_file: Path):
    """检测对 data_lake/reports/signals/paper 运行产物的直接写操作。"""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except (SyntaxError, UnicodeDecodeError):
        return []

    artifact_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _mentions_runtime_artifact(node.value):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    artifact_vars.add(tgt.id)

    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            obj = node.func.value
            mentions = _mentions_runtime_artifact(obj) or (
                isinstance(obj, ast.Name) and obj.id in artifact_vars
            )
            if mentions and attr in ("write_text", "write_bytes"):
                hits.append(node.lineno)
            if mentions and attr == "open" and not _call_opens_for_read(node, mode_arg_index=0):
                hits.append(node.lineno)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            if node.args and (
                _mentions_runtime_artifact(node.args[0])
                or (isinstance(node.args[0], ast.Name) and node.args[0].id in artifact_vars)
            ) and not _call_opens_for_read(node, mode_arg_index=1):
                hits.append(node.lineno)
    return hits


def service_action_permission_violations(py_file: Path):
    """services.actions 高风险动作必须显式经 jobs/action_guard。"""
    mods = imported_modules(py_file)
    targets = [target for target, _lineno in mods]
    has_permission_boundary = any(
        target == "services.actions.jobs"
        or target.startswith("services.actions.jobs.")
        or target == "services.actions.action_guard"
        or target.startswith("services.actions.action_guard.")
        for target in targets
    )
    high_risk_imports = [
        (target, lineno)
        for target, lineno in mods
        if target == "workflow.promote"
        or target.startswith("workflow.promote.")
        or target == "strategy_registry"
        or target.startswith("strategy_registry.")
    ]
    if high_risk_imports and not has_permission_boundary:
        return [lineno for _target, lineno in high_risk_imports]
    return []


def _call_opens_for_read(node: ast.Call, *, mode_arg_index: int) -> bool:
    """True for open()/Path.open() calls whose mode can read."""
    mode = "r"
    if len(node.args) > mode_arg_index and isinstance(node.args[mode_arg_index], ast.Constant):
        mode = str(node.args[mode_arg_index].value)
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = str(kw.value.value)
    return "r" in mode or "+" in mode


def check() -> int:
    violations = []
    for py_file in sorted(ROOT.rglob("*.py")):
        if any(part in EXCLUDE_DIRS for part in py_file.relative_to(ROOT).parts):
            continue
        mod = module_path(py_file)
        rel = py_file.relative_to(ROOT)
        # 台账唯一写入口检查
        is_test = "tests" in py_file.relative_to(ROOT).parts
        if py_file.name not in REGISTRY_WRITER_ALLOWLIST and not is_test:
            for lineno in registry_write_violations(py_file):
                violations.append((rel, lineno,
                    f"直写 {REGISTRY_FILE} — 台账只能经 strategy_registry.register()"))
        if (mod == "api" or mod.startswith("api.")) and str(rel) not in API_ARTIFACT_READ_ALLOWLIST:
            for lineno in api_runtime_artifact_read_violations(py_file):
                violations.append((rel, lineno,
                    "api 直读运行产物 — HTTP 层只能经 services.read/contracts"))
            if not any(
                target == "services.actions.action_guard" or target.startswith("services.actions.action_guard.")
                for target, _lineno in imported_modules(py_file)
            ):
                for lineno in runtime_artifact_write_violations(py_file):
                    violations.append((rel, lineno,
                        "api 直写运行产物 — 写动作必须经 services.actions.action_guard"))
        if mod.startswith("services.actions.") and py_file.name not in {"action_guard.py", "jobs.py"}:
            for lineno in service_action_permission_violations(py_file):
                violations.append((rel, lineno,
                    "services.actions 高风险动作必须经 jobs 或 action_guard 接缝"))
        # 全局禁止import检查(任何文件都不得import这些已退场模块)
        for target, lineno in imported_modules(py_file):
            for forbidden in GLOBAL_FORBIDDEN_IMPORTS:
                if target == forbidden or target.startswith(forbidden + "."):
                    violations.append((rel, lineno, f"import {target} — 已退场模块,禁止导入"))
        for source_prefix, forbidden_targets in FORBIDDEN_EDGES:
            if mod == source_prefix or mod.startswith(source_prefix):
                for target, lineno in imported_modules(py_file):
                    for forbidden in forbidden_targets:
                        if target == forbidden.rstrip(".") or target.startswith(forbidden):
                            if (str(rel), lineno) in ALLOWED_EXCEPTIONS:
                                continue
                            if (str(rel), target) in ALLOWED_IMPORT_EXCEPTIONS:
                                continue
                            violations.append((rel, lineno,
                                f"import {target} — 违反分层:{source_prefix} 不得依赖该前缀"))

    if violations:
        print("发现依赖/写入违规:")
        for f, lineno, msg in violations:
            print(f"  {f}:{lineno}  {msg}")
        return 1

    print("分层依赖检查通过,无违规。")
    return 0


if __name__ == "__main__":
    sys.exit(check())
