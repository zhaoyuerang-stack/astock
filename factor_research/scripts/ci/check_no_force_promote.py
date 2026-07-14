"""防 force-promote 回归守卫(根因分析 #1 / ADR-017)。

历史:`bulk_promote.py` 曾 force=True + run_marginal=False 把 9-Gate REJECTED 的候选强制入册。
本守卫 AST 扫**自动晋级脚本**,禁止其中出现:
  - 任意调用的 `force=True`(跳过 phase1/2 防未来 + 图谱门)
  - `run_marginal=False`(跳过边际残差去冗余)

扫描集 = **默认扫描**(2026-07-11 加固):`scripts/ops/**` 与 `services/actions/**` 中所有
AST 判定 import 了 workflow.promote / workflow.from_factory 的文件——新增自动 promoter
自动纳入,不再靠人工维护枚举名单(deny-list 会默认逃逸)。
注意:library 层 `workflow/promote.py` 的 `--force` 是**人工逃生口**(CLI,带警告),不在扫描集——
自动脚本绝不能用,人工单次可用。

只读 AST,违规则 exit 1。检测函数吃源码字符串/可注入 root,便于 fixture 测试。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 自动晋级脚本所在目录(相对 root);其中 import 了晋级通道的文件全部自动纳入扫描
AUTO_PROMOTE_DIRS = ["scripts/ops", "services/actions"]
# 判定"这是个自动晋级脚本"的 import 目标前缀
PROMOTE_IMPORT_PREFIXES = ("workflow.promote", "workflow.from_factory")


def _imports_promote_channel(tree: ast.AST) -> bool:
    """AST 判定:文件是否 import 了晋级通道(workflow.promote / workflow.from_factory)。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PROMOTE_IMPORT_PREFIXES):
                    return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith(PROMOTE_IMPORT_PREFIXES):
                return True
            if mod == "workflow" and any(
                a.name in ("promote", "from_factory") for a in node.names
            ):
                return True
    return False


def discover_auto_promote_files(root: Path | None = None) -> list[Path]:
    """默认扫描:AUTO_PROMOTE_DIRS 下所有 import 了晋级通道的 .py 文件(递归)。"""
    base = root or ROOT
    out: list[Path] = []
    for rel in AUTO_PROMOTE_DIRS:
        d = base / rel
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            if _imports_promote_channel(tree):
                out.append(p)
    return out


def scan_source(src: str, label: str = "") -> list[str]:
    """AST 扫源码:返回 [violation msg]。检测调用里的 force=True / run_marginal=False。"""
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"[{label}] 语法错误,无法扫描: {e}"]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "force" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                out.append(f"[{label}:L{kw.value.lineno}] 调用含 force=True —— 自动晋级禁用强制入册(绕过 phase1/2 防未来门)")
            if kw.arg == "run_marginal" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                out.append(f"[{label}:L{kw.value.lineno}] 调用含 run_marginal=False —— 自动晋级禁用跳过边际残差去冗余")
    return out


def check(root: Path | None = None) -> int:
    base = root or ROOT
    files = discover_auto_promote_files(base)
    violations = []
    for p in files:
        rel = str(p.relative_to(base))
        violations += scan_source(p.read_text(encoding="utf-8"), label=rel)
    if violations:
        print("发现 force-promote 橡皮图章违规:")
        for v in violations:
            print(f"  {v}")
        return 1
    print(f"force-promote 守卫通过:{len(files)} 个自动晋级脚本(默认扫描)无 force=True / run_marginal=False。")
    return 0


if __name__ == "__main__":
    sys.exit(check())
