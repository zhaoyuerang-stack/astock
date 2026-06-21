"""防 force-promote 回归守卫(根因分析 #1 / ADR-017)。

历史:`bulk_promote.py` 曾 force=True + run_marginal=False 把 9-Gate REJECTED 的候选强制入册。
本守卫 AST 扫**自动晋级脚本**(无人值守批量 promote 的 ops 脚本),禁止其中出现:
  - 任意调用的 `force=True`(跳过 phase1/2 防未来 + 图谱门)
  - `run_marginal=False`(跳过边际残差去冗余)
注意:library 层 `workflow/promote.py` 的 `--force` 是**人工逃生口**(CLI,带警告),不在扫描集——
自动脚本绝不能用,人工单次可用。

只读 AST,违规则 exit 1。检测函数吃源码字符串,便于 fixture 测试。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 无人值守/批量晋级脚本(新增自动 promoter 须加进来)
AUTO_PROMOTE_FILES = [
    "scripts/ops/bulk_promote.py",
    "scripts/ops/scheduled_factor_search.py",
]


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


def check() -> int:
    violations = []
    for rel in AUTO_PROMOTE_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        violations += scan_source(p.read_text(), label=rel)
    if violations:
        print("发现 force-promote 橡皮图章违规:")
        for v in violations:
            print(f"  {v}")
        return 1
    print("force-promote 守卫通过:自动晋级脚本无 force=True / run_marginal=False。")
    return 0


if __name__ == "__main__":
    sys.exit(check())
