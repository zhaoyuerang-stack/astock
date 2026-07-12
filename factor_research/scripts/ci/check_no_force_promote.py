"""防 force-promote / 跳过 9-Gate 回归守卫(根因分析 #1 / ADR-017 + 审计#8)。

历史:
  - `bulk_promote.py` 曾 force=True + run_marginal=False 把 9-Gate REJECTED 的候选强制入册
  - `promote_spec(run_nine_gate=False)` 默认曾允许人工/factory 堆无 DSR 的候选台账

本守卫 AST 扫**自动/CLI 晋级入口**,禁止其中出现:
  - 任意调用的 `force=True`(跳过 phase1/2 防未来 + 图谱门)
  - `run_marginal=False`(跳过边际残差去冗余)
  - `run_nine_gate=False`(跳过 9-Gate/DSR 回填)

说明:
  - library 层 ``Phase4Register.register(force=...)`` 的 force **只能**覆盖 phase1/2/3,
    holdout 金库闸始终硬阻断(见 phase4_register.py)。
  - CLI 可保留 ``--force`` 接线为 ``force=args.force``(非常量 True),供人工覆盖 phase 门;
    本守卫只拦字面 ``force=True`` / ``run_nine_gate=False`` 的橡皮图章。
  - ``promote_spec`` 库函数默认已为 ``run_nine_gate=True``;调试可显式 False,但不得写进
    自动/CLI 晋级入口。

只读 AST,违规则 exit 1。检测函数吃源码字符串,便于 fixture 测试。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 无人值守/批量晋级 + 工厂 CLI 入口(新增 promoter 须加进来)
AUTO_PROMOTE_FILES = [
    "scripts/ops/bulk_promote.py",
    "scripts/ops/scheduled_factor_search.py",
    "apps/factory_cli.py",
    "services/actions/autoresearch.py",
    "workflow/promote.py",  # CLI __main__ 与默认签名旁路不得字面关闭 9-Gate
]


def scan_source(src: str, label: str = "") -> list[str]:
    """AST 扫源码:返回 [violation msg]。

    检测调用里的 force=True / run_marginal=False / run_nine_gate=False。
    """
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
                out.append(
                    f"[{label}:L{kw.value.lineno}] 调用含 force=True —— "
                    "晋级入口禁用字面强制入册(绕过 phase1/2 防未来门)"
                )
            if kw.arg == "run_marginal" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                out.append(
                    f"[{label}:L{kw.value.lineno}] 调用含 run_marginal=False —— "
                    "晋级入口禁用跳过边际残差去冗余"
                )
            if kw.arg == "run_nine_gate" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                out.append(
                    f"[{label}:L{kw.value.lineno}] 调用含 run_nine_gate=False —— "
                    "晋级入口禁用跳过 9-Gate/DSR 回填(默认必须跑)"
                )
    return out


def check() -> int:
    violations = []
    for rel in AUTO_PROMOTE_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        violations += scan_source(p.read_text(encoding="utf-8"), label=rel)
    if violations:
        print("发现 force-promote / 跳过 9-Gate 橡皮图章违规:")
        for v in violations:
            print(f"  {v}")
        return 1
    print(
        "force-promote 守卫通过:自动/CLI 晋级入口无字面 "
        "force=True / run_marginal=False / run_nine_gate=False。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(check())
