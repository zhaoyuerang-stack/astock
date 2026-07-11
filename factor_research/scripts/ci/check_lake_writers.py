"""数据湖唯一写入口守卫——湖核心/证据区只允许数据层模块写入。

背景(2026-06-12 事故):ad-hoc 修复脚本直写 daily_all 且不更新 manifest,
造成数据与台账失联;类比策略侧"台账唯一写入口 = strategy_registry"铁律,
数据侧同样需要:**写 data_lake 核心区(price/fundamental/meta/capital/global/global_raw/
global_quarantine)的
代码必须住在 lake/ 或 scripts/data/(含 scripts/repair/ 修复工具)**。

静态检查:凡写方法(to_parquet/to_csv/write_text/write_bytes/open 写模式)且引用受保护湖路径、
又不在允许目录的文件 → 违规。
LEGACY 名单是显式记录的迁移欠债,新增违规直接报错。
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_PREFIXES = ("lake/", "scripts/data/", "scripts/repair/", "tests/")
# 历史欠债名单。必须保持为空;新增违规不允许用白名单掩盖。
LEGACY = set()
PROTECTED_LAKE = re.compile(
    r"data_lake[/\"']\s*(?:/\s*)?(?:price|fundamental|meta|capital|global|global_raw|global_quarantine|version_returns)"
    r"|data_lake/(?:price|fundamental|meta|capital|global|global_raw|global_quarantine|version_returns)"
    r"|[\"']data_lake[\"']\s*\)?\s*/\s*[\"'](?:price|fundamental|meta|capital|global|global_raw|global_quarantine|version_returns)[\"']"
)
WRITE_METHODS = ("to_parquet", "to_csv", "write_text", "write_bytes")


def _is_allowed(rel: str) -> bool:
    return rel.startswith(ALLOWED_PREFIXES) or rel in LEGACY


def _const_strings(node: ast.AST) -> list[str]:
    return [
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def _mentions_protected_path(node: ast.AST) -> bool:
    strings = _const_strings(node)
    joined = "/".join(strings)
    if PROTECTED_LAKE.search(joined):
        return True
    protected_parts = {"price", "fundamental", "meta", "capital", "global", "global_raw", "global_quarantine", "version_returns"}
    return "data_lake" in strings and any(s in protected_parts for s in strings)


def _collect_protected_path_vars(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not _mentions_protected_path(node.value):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _uses_protected_path(node: ast.AST, protected_vars: set[str]) -> bool:
    if _mentions_protected_path(node):
        return True
    return any(isinstance(n, ast.Name) and n.id in protected_vars for n in ast.walk(node))


def _scan_tree_for_writes(tree: ast.AST) -> bool:
    protected_vars = _collect_protected_path_vars(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in WRITE_METHODS:
            target_nodes = list(node.args) + [node.func.value]
            if any(_uses_protected_path(t, protected_vars) for t in target_nodes):
                return True
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = ""
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(c in mode for c in ("w", "a", "+")) and node.args:
                if _uses_protected_path(node.args[0], protected_vars):
                    return True
    return False


def _open_write_violation(src: str) -> bool:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    return _scan_tree_for_writes(tree)


def scan_source(src: str, *, rel: str) -> list[str]:
    if _is_allowed(rel):
        return []
    if _open_write_violation(src):
        return [rel]
    return []


def main() -> int:
    files = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()

    violations = []
    for rel in files:
        if rel.startswith(ALLOWED_PREFIXES) or rel in LEGACY:
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (FileNotFoundError, UnicodeDecodeError):
            continue
        violations.extend(scan_source(text, rel=rel))

    if violations:
        print("🚨 数据湖唯一写入口违规(写湖核心区的代码必须在 lake/ 或 scripts/data/):")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(f"数据湖写入口检查通过({len(files)} 个文件,legacy 豁免 {len(LEGACY)} 个)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
