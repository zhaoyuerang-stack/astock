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

# 架构评审(scripts/ 去库化)发现 scripts/ 目录事实上藏了两条 canonical→scripts
# 反向依赖边:lake.version_returns 反向 import scripts/ci/check_cost_model_pin
# 取 cost_hash;run_daily.py(生产层)反向 import scripts.data.update_lake。两条
# 已分别迁至 governance/cost_pin.py 与 lake/update.py。为防止同类边复发,对
# run_daily / lake. / core.engine / core.analysis / engine. 这五个 src 前缀把
# 原本只挡 scripts.research. 的黑名单扩为挡整个 scripts.(含 scripts.data /
# scripts.ops / scripts.ci 等) —— 这五者是生产/回测/湖三层最底层,不该依赖
# scripts/ 下任何子目录。其余 src 前缀(strategies./factors./policy./
# scripts.data./scripts.ops. 等)未改动,含 workflow/promote.py 对
# scripts.research.run_nine_gates_all 的已知遗留依赖(另案处理,本单不动)。
FORBIDDEN_EDGES = [
    ("run_daily", ["factory.", "scripts.", "workflow.", "knowledge.", "api.", "services."]),
    ("strategies.", ["factory.", "scripts.research.", "workflow.", "knowledge.", "api.", "services."]),
    ("factors.", ["factory.", "strategies.", "scripts.research.", "workflow.", "core.", "knowledge.", "api.", "services."]),
    # policy 是候选/持仓硬约束的底层叶子(candidate_filters/constraints),被 factors.veto
    # 等兼容 wrapper 反向 import(factors→policy),因此 policy 必须停在 factors 之下:
    # 不得 import factors(否则 factors↔policy 成环)、engine/core,也不得倒灌
    # strategies/factory/workflow/scripts.research 等上层。只可依赖 stdlib/pandas/lake/contracts。
    ("policy.", ["factors.", "engine.", "core.", "factory.", "strategies.",
                 "scripts.research.", "workflow.", "knowledge.", "api.", "services."]),
    ("lake.", ["factors.", "strategies.", "core.", "factory.", "scripts.", "knowledge.", "api.", "services."]),
    ("core.engine", ["factory.", "strategies.", "scripts.", "workflow.", "knowledge.", "api.", "services."]),
    ("core.analysis", ["factory.", "strategies.", "scripts.", "workflow.", "knowledge.", "api.", "services."]),
    # engine/ 是 core.engine 的底层引擎叶子(metrics/composer/portfolio/factor_analysis),
    # 必须停在最底层:不得反向依赖 factors(状态/因子层)、组合构建层(strategies)或探索层
    # (factory/scripts.research/workflow)。黑名单原先漏了这个与 core/ 平级的顶层目录,
    # 导致 regime.py/strategy_composer.py 倒灌未被发现;两者已迁出至 factory/。
    ("engine.", ["factors.", "factory.", "strategies.", "scripts.", "workflow."]),
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
    # contracts 是纯 DTO 叶子:只依赖 pydantic + stdlib,不得依赖任何业务层
    ("contracts.", ["core.", "lake.", "factors.", "strategies.", "factory.", "workflow.",
                    "engine.", "metasearch.", "knowledge.", "scripts.", "services.", "api."]),
]

# 全局禁止import的模块(无论从哪一层):已退场的兼容层 / 死接口。
# core.backtest 已于解耦收尾阶段退场(重命名为 _deprecated_backtest.py.bak),
# 唯一回测路径是 core.engine.BacktestEngine;新代码绝不能再 import core.backtest。
GLOBAL_FORBIDDEN_IMPORTS = ["core.backtest"]

# 行号级例外集:已于 2026-07-18 清零并冻结——最后一条(search.py walk_forward)
# 因上方插入 4 行代码就失配,实证行号钉脆弱;已迁至下方目标级白名单。
# 历史教训:原 5 条豁免中 4 条指向随 Phase1 框架搬入的死桥接(to_signal()/
# default_*_builder(),其 import 目标 core.signals/EngineConfig/core.interfaces
# 在本仓从未存在),零调用零测试,借行号白名单隐身;已在 P0-1 清理中随死代码
# 一并删除。**新增例外一律用 ALLOWED_IMPORT_EXCEPTIONS,不得再加行号钉。**
ALLOWED_EXCEPTIONS: set[tuple[str, int]] = set()

# 文件 + import 目标级例外:比行号稳定,但仍要求新增桥接显式登记。
ALLOWED_IMPORT_EXCEPTIONS = {
    # walk_forward 评估在 search.py 函数体内延迟导入 core.analysis(避免模块级
    # 循环依赖),有意为之;原行号钉 (search.py, 275) 迁移至此(2026-07-18)。
    ("factors/alpha/search.py", "core.analysis.walk_forward"),
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
    # 周度组合再构成(WS-D):只读在册版本清单定位 version_returns 序列,零台账写入。
    ("scripts/ops/scheduled_portfolio_recompose.py", "strategy_registry"),
}


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
