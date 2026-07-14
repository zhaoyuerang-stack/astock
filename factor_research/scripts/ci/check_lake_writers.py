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

ALLOWED_PREFIXES = ("lake/", "scripts/data/", "scripts/repair/")
# 历史欠债名单。必须保持为空;新增违规不允许用白名单掩盖。
LEGACY = set()
PROTECTED_LAKE = re.compile(r"(?:^|[/\\])data_lake(?:[/\\]|$)|[\"']data_lake[\"']")
WRITE_METHODS = (
    "to_parquet", "to_csv", "to_feather", "to_pickle", "to_json", "to_hdf",
    "write_text", "write_bytes",
)
TEMP_ROOT_NAMES = {"tmp_path", "tmpdir", "tmp_dir", "temp_dir", "temporary_directory"}
DESTINATION_KEYWORDS = {
    "path", "path_or_buf", "filepath_or_buffer", "filename", "file", "fname",
    "fp", "dst", "destination",
}


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
    return "data_lake" in strings or PROTECTED_LAKE.search(joined) is not None


def _assignments(tree: ast.AST) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            out[node.target.id] = node.value
    return out


def _is_path_expression(node: ast.AST) -> bool:
    """Whether an assignment constructs/aliases a path rather than reads data."""
    if isinstance(node, (ast.Constant, ast.Name, ast.Attribute)):
        return True
    if isinstance(node, ast.BinOp):
        return _is_path_expression(node.left) and _is_path_expression(node.right)
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        return name in {"Path", "joinpath", "resolve", "with_name", "with_suffix"}
    return False


def _collect_protected_path_vars(tree: ast.AST, assignments: dict[str, ast.AST]) -> set[str]:
    lake_roots: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, value in assignments.items():
            if name in lake_roots:
                continue
            if not _is_path_expression(value):
                continue
            strings = _const_strings(value)
            if "data_lake" in strings or any(
                isinstance(part, ast.Name) and part.id in lake_roots
                for part in ast.walk(value)
            ):
                lake_roots.add(name)
                changed = True

    names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, value in assignments.items():
            if name in names:
                continue
            if not _is_path_expression(value):
                continue
            if _mentions_protected_path(value) or any(
                isinstance(part, ast.Name) and part.id in names
                for part in ast.walk(value)
            ) or any(
                isinstance(part, ast.Name) and part.id in lake_roots
                for part in ast.walk(value)
            ):
                names.add(name)
                changed = True
    return names


def _is_temp_rooted(node: ast.AST, assignments: dict[str, ast.AST], seen: set[str] | None = None) -> bool:
    seen = set(seen or ())
    if isinstance(node, ast.Name):
        if node.id in TEMP_ROOT_NAMES:
            return True
        if node.id in seen or node.id not in assignments:
            return False
        return _is_temp_rooted(assignments[node.id], assignments, seen | {node.id})
    if isinstance(node, ast.Attribute):
        return node.attr in TEMP_ROOT_NAMES or _is_temp_rooted(node.value, assignments, seen)
    if isinstance(node, ast.BinOp):
        return _is_temp_rooted(node.left, assignments, seen) or _is_temp_rooted(node.right, assignments, seen)
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if name in {"TemporaryDirectory", "mkdtemp"}:
            return True
        return any(_is_temp_rooted(arg, assignments, seen) for arg in node.args)
    return False


def _write_targets(node: ast.Call) -> list[ast.AST]:
    if isinstance(node.func, ast.Attribute) and node.func.attr in WRITE_METHODS:
        targets = [node.func.value]
        if node.func.attr.startswith("to_") and node.args:
            targets.append(node.args[0])
        targets.extend(
            keyword.value for keyword in node.keywords
            if keyword.arg in DESTINATION_KEYWORDS
        )
        return targets
    name = node.func.attr if isinstance(node.func, ast.Attribute) else (
        node.func.id if isinstance(node.func, ast.Name) else ""
    )
    # Serialization/copy APIs that take the destination as a positional arg.
    if name in {"dump"}:
        targets = [node.args[1]] if len(node.args) > 1 else []
        targets.extend(keyword.value for keyword in node.keywords if keyword.arg in {"fp", "file"})
        return targets
    if name in {"save", "savez", "savez_compressed"}:
        targets = [node.args[0]] if node.args else []
        targets.extend(keyword.value for keyword in node.keywords if keyword.arg in DESTINATION_KEYWORDS)
        return targets
    if name in {"copy", "copy2", "copyfile", "move"}:
        targets = [node.args[1]] if len(node.args) > 1 else []
        targets.extend(keyword.value for keyword in node.keywords if keyword.arg in {"dst", "destination"})
        return targets
    return []


def _uses_protected_path(node: ast.AST, protected_vars: set[str]) -> bool:
    if _mentions_protected_path(node):
        return True
    return any(isinstance(n, ast.Name) and n.id in protected_vars for n in ast.walk(node))


def _inside_expected_runtime_block(node: ast.AST) -> bool:
    """Allow a negative test only when it asserts the runtime barrier's exact failure."""
    parent = getattr(node, "_lake_guard_parent", None)
    while parent is not None:
        if isinstance(parent, ast.With):
            for item in parent.items:
                call = item.context_expr
                if not isinstance(call, ast.Call):
                    continue
                name = call.func.attr if isinstance(call.func, ast.Attribute) else ""
                exception = call.args[0].id if call.args and isinstance(call.args[0], ast.Name) else ""
                match = next(
                    (
                        keyword.value.value
                        for keyword in call.keywords
                        if keyword.arg == "match"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ),
                    "",
                )
                if name == "raises" and exception == "RuntimeError" and "canonical data_lake forbidden" in match:
                    return True
        parent = getattr(parent, "_lake_guard_parent", None)
    return False


def _scan_tree_for_writes(tree: ast.AST, *, allow_temp_paths: bool = False) -> bool:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_lake_guard_parent", parent)
    assignments = _assignments(tree)
    protected_vars = _collect_protected_path_vars(tree, assignments)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target_nodes = _write_targets(node)
        if any(
            _uses_protected_path(target, protected_vars)
            and not (allow_temp_paths and _is_temp_rooted(target, assignments))
            for target in target_nodes
        ):
            if not (allow_temp_paths and _inside_expected_runtime_block(node)):
                return True
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in {"rename", "replace"}
            and (len(node.args) <= 1 or any(
                keyword.arg in DESTINATION_KEYWORDS for keyword in node.keywords
            ))
        ):
            target_nodes = list(node.args) + [node.func.value] + [
                keyword.value for keyword in node.keywords
                if keyword.arg in DESTINATION_KEYWORDS
            ]
            if any(
                _uses_protected_path(target, protected_vars)
                and not (allow_temp_paths and _is_temp_rooted(target, assignments))
                for target in target_nodes
            ):
                if not (allow_temp_paths and _inside_expected_runtime_block(node)):
                    return True
        is_builtin_open = isinstance(node.func, ast.Name) and node.func.id == "open"
        is_path_open = isinstance(node.func, ast.Attribute) and node.func.attr == "open"
        if is_builtin_open or is_path_open:
            mode = ""
            mode_index = 1 if is_builtin_open else 0
            if len(node.args) > mode_index and isinstance(node.args[mode_index], ast.Constant):
                mode = str(node.args[mode_index].value)
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            target = None
            if is_builtin_open:
                if node.args:
                    target = node.args[0]
                else:
                    target = next(
                        (keyword.value for keyword in node.keywords if keyword.arg in {"file", "path"}),
                        None,
                    )
            elif is_path_open:
                target = node.func.value
            if any(c in mode for c in ("w", "a", "x", "+")) and target is not None:
                if (
                    _uses_protected_path(target, protected_vars)
                    and not (allow_temp_paths and _is_temp_rooted(target, assignments))
                ):
                    if not (allow_temp_paths and _inside_expected_runtime_block(node)):
                        return True
    return False


def _open_write_violation(src: str, *, allow_temp_paths: bool = False) -> bool:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    return _scan_tree_for_writes(tree, allow_temp_paths=allow_temp_paths)


def scan_source(src: str, *, rel: str) -> list[str]:
    if _is_allowed(rel):
        return []
    if _open_write_violation(src, allow_temp_paths=rel.startswith("tests/")):
        return [rel]
    return []


def discover_python_files(root: Path = ROOT) -> list[str]:
    """Return governed Python paths in a worktree or a source archive.

    Git mode intentionally includes untracked files so a shared-worktree WIP cannot
    introduce an unguarded canonical writer.  A release/source archive has no
    ``.git`` metadata, so conservatively scan every Python file on disk instead of
    crashing or, worse, silently checking nothing.
    """
    try:
        output = subprocess.run(
            [
                "git", "ls-files", "--cached", "--others", "--exclude-standard",
                "--", "*.py",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        return sorted(set(output))
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            str(path.relative_to(root))
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts
        )


def main() -> int:
    files = discover_python_files()

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
