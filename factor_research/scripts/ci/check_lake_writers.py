"""数据湖唯一写入口守卫——湖区只允许数据层模块写入。

背景(2026-06-12 事故):ad-hoc 修复脚本直写 daily_all 且不更新 manifest,
造成数据与台账失联;类比策略侧"台账唯一写入口 = strategy_registry"铁律,
数据侧同样需要:**写 data_lake 任意子目录的代码必须住在 lake/ 或
scripts/data/(含 scripts/repair/ 修复工具)**。

静态检查(ADR-038 决策一,AST 级):
  - 写动词:{to_parquet, to_csv, to_pickle, write_table}(方法或 Name/Attribute 调用)
  - 仅当写调用的**实参路径表达式**可追溯到 data_lake 引用才判违规
    (字符串字面量,或经简单赋值传播的变量——照 check_layer_deps
    registry_write_violations 变量绑定范式 + 固定点传播)
  - 文件枚举:磁盘 rglob;排除 data_lake/、__pycache__、.pytest_cache;
    tests/ 与 scripts/ci/ 豁免;ALLOWED_PREFIXES 内放行
  - 哲学:防的是**写湖**,不是提及湖(读湖 + to_csv 到 reports/ 必绿)

存量命中进 PENDING_REMEDIATION(响而不阻),新增即红。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_PREFIXES = ("lake/", "scripts/data/", "scripts/repair/", "tests/", "scripts/ci/")
WRITE_METHODS = frozenset({"to_parquet", "to_csv", "to_pickle", "write_table"})
WRITE_FUNCS = frozenset({"write_table"})

# 存量欠债。响而不阻;真写湖者应改走 lake/ canonical writer 或 scoped 区(ADR-038)。
# ADR-038 决策一:6 条文件级共现误报已随 AST 升级销账;余 factor_store 两系归决策三。
PENDING_REMEDIATION: dict[str, str] = {
    "factor_store/store.py":
        "迁移欠债:to_parquet 写 data_lake/factor_store;应改走 lake/ 或登记为 canonical 区",
    "factors/autoresearch_dsl.py":
        "迁移欠债:to_parquet 写 data_lake/factor_store/panels 缓存",
}


def _is_exempt(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    if rel.startswith(ALLOWED_PREFIXES):
        return True
    if "/tests/" in f"/{rel}" or rel.startswith("tests/"):
        return True
    return False


def iter_py_files(root: Path) -> list[Path]:
    """磁盘 rglob 全部 .py,排除 data_lake/、缓存目录。"""
    out: list[Path] = []
    for p in sorted(root.rglob("*.py")):
        if any(part in {"data_lake", "__pycache__", ".pytest_cache"} for part in p.parts):
            continue
        out.append(p)
    return out


def _str_mentions_lake(value: object) -> bool:
    """字符串是否含 data_lake 路径引用(字面量 data_lake/... 或组件 'data_lake')。"""
    if not isinstance(value, str):
        return False
    return "data_lake/" in value or value == "data_lake" or "/data_lake/" in value


def _node_mentions_lake_literal(node: ast.AST | None) -> bool:
    if node is None:
        return False
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and _str_mentions_lake(n.value):
            return True
    return False


def _expr_refs_lake(node: ast.AST | None, lake_vars: set[str]) -> bool:
    """路径表达式是否可追溯到 data_lake(字面量或已绑定变量)。"""
    if node is None:
        return False
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and _str_mentions_lake(n.value):
            return True
        if isinstance(n, ast.Name) and n.id in lake_vars:
            return True
    return False


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: list[str] = []
    for tgt in targets:
        if isinstance(tgt, ast.Name):
            names.append(tgt.id)
    return names


def _collect_lake_vars(tree: ast.AST) -> set[str]:
    """简单赋值传播:值含 lake 字面量或已绑定 lake 变量 → 目标名入集(固定点)。"""
    assignments: list[ast.Assign | ast.AnnAssign] = [
        n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign))
    ]
    lake_vars: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in assignments:
            value = node.value
            if value is None:
                continue
            if _expr_refs_lake(value, lake_vars) or _node_mentions_lake_literal(value):
                for name in _assigned_names(node):
                    if name not in lake_vars:
                        lake_vars.add(name)
                        changed = True
    return lake_vars


def _call_write_path_args(node: ast.Call) -> list[ast.AST]:
    """提取写调用中可能承载路径的实参(含关键字)。"""
    args: list[ast.AST] = []
    func = node.func
    is_method = isinstance(func, ast.Attribute) and func.attr in WRITE_METHODS
    is_func = (
        (isinstance(func, ast.Name) and func.id in WRITE_FUNCS)
        or (isinstance(func, ast.Attribute) and func.attr in WRITE_FUNCS)
    )
    if not (is_method or is_func):
        return args
    # to_*(path) 首参即路径;write_table(table, where) 第二参起为路径
    if is_method and isinstance(func, ast.Attribute) and func.attr == "write_table":
        args.extend(node.args[1:] if len(node.args) > 1 else [])
    elif is_func and (
        (isinstance(func, ast.Name) and func.id == "write_table")
        or (isinstance(func, ast.Attribute) and func.attr == "write_table")
    ):
        args.extend(node.args[1:] if len(node.args) > 1 else [])
    else:
        # to_parquet / to_csv / to_pickle:全部位置实参都可能是路径
        args.extend(node.args)
    for kw in node.keywords:
        if kw.arg in {
            None,
            "path",
            "path_or_buf",
            "filepath_or_buffer",
            "where",
            "fname",
        } or kw.arg is None:
            args.append(kw.value)
        elif is_method or is_func:
            # 保守:关键字值若直接/间接含 lake 也算(path=..., buf=...)
            args.append(kw.value)
    return args


def source_has_lake_write(src: str) -> bool:
    """AST:写调用实参路径可追溯到 data_lake → True。语法错误不判违规。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    lake_vars = _collect_lake_vars(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for arg in _call_write_path_args(node):
            if _expr_refs_lake(arg, lake_vars):
                return True
    return False


# 向后兼容旧测试名
def file_is_violation(text: str) -> bool:
    """同 source_has_lake_write(ADR-038 AST 级)。"""
    return source_has_lake_write(text)


def scan(root: Path | None = None) -> list[str]:
    """返回全部 AST 写湖命中(含 PENDING 候选),供测试断言。"""
    base = root or ROOT
    hits: list[str] = []
    for p in iter_py_files(base):
        try:
            rel = str(p.relative_to(base)).replace("\\", "/")
        except ValueError:
            continue
        if _is_exempt(rel):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if source_has_lake_write(text):
            hits.append(rel)
    return hits


def main(root: Path | None = None) -> int:
    base = root or ROOT
    files = iter_py_files(base)
    raw_hits = scan(base)

    new_v = [h for h in raw_hits if h not in PENDING_REMEDIATION]
    pending = [h for h in raw_hits if h in PENDING_REMEDIATION]
    no_longer = [k for k in PENDING_REMEDIATION if k not in raw_hits]

    for h in pending:
        print(f"  ⚠️ 待处置(基线): {h} — {PENDING_REMEDIATION[h]}")
    for k in no_longer:
        print(f"  ℹ️ 基线项已修复或不再命中,请从 PENDING_REMEDIATION 移除: {k}")

    if new_v:
        print("🚨 数据湖唯一写入口违规(写湖区的代码必须在 lake/ 或 scripts/data/):")
        for v in new_v:
            print(f"  - {v}")
        return 1
    print(
        f"数据湖写入口检查通过({len(files)} 个文件扫描,"
        f"{len(pending)} 项待处置已基线)。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
