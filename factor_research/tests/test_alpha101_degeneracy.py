"""alpha101 搜索白名单不得含机械退化/近重复因子(n_trials 诚实)。

护栏:
  · AST 含 close-close 等恒常子项 → 不得在 ALLOWED_FACTORS
  · 已知退化/短收益簇重复项 → 不得在 ALLOWED_FACTORS 与 DSL _FACTOR_CALLS
  · 实现可保留在 alpha101.py 供对照,但不可再被工厂搜索
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.autoresearch.registry import ALLOWED_FACTORS
from factors import alpha101
from factors.autoresearch_dsl import _FACTOR_CALLS

# 机械扫描 + 数值近重复审计后移出搜索宇宙的因子
_BANNED_SEARCHABLE = frozenset({
    "alpha_005",   # close-close 常数子项 → price_to_ma 同信息
    "alpha_020",   # 与 alpha_009 短收益簇 |秩相关|≈1
    "alpha_022",
    "alpha_024",
    "alpha_033",
    "alpha_049",   # alpha_024 逐字双胞胎
})


def test_banned_alphas_not_in_search_whitelist():
    present = sorted(_BANNED_SEARCHABLE & set(ALLOWED_FACTORS))
    assert not present, f"退化/近重复 alpha 仍在 ALLOWED_FACTORS: {present}"


def test_banned_alphas_not_in_dsl_calls():
    present = sorted(_BANNED_SEARCHABLE & set(_FACTOR_CALLS))
    assert not present, f"退化/近重复 alpha 仍在 DSL _FACTOR_CALLS: {present}"


def test_no_close_minus_close_in_searchable_alphas():
    """可搜索的 alpha_* 源码不得含 close-close 恒常子项。"""
    src = inspect.getsource(alpha101)
    tree = ast.parse(src)
    offenders = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("alpha_"):
            continue
        if node.name not in ALLOWED_FACTORS:
            continue
        for n in ast.walk(node):
            if (
                isinstance(n, ast.BinOp)
                and isinstance(n.op, ast.Sub)
                and isinstance(n.left, ast.Name)
                and isinstance(n.right, ast.Name)
                and n.left.id == n.right.id
            ):
                offenders.append(f"{node.name}: {n.left.id}-{n.right.id}")
    assert not offenders, f"可搜索 alpha 含恒常自减子项: {offenders}"


def test_alpha_005_still_exists_for_audit():
    """实现保留(R-ARCH-005:废弃可留源,但不可作新搜索入口)。"""
    assert hasattr(alpha101, "alpha_005")
    assert "alpha_005" not in ALLOWED_FACTORS


if __name__ == "__main__":
    test_banned_alphas_not_in_search_whitelist()
    test_banned_alphas_not_in_dsl_calls()
    test_no_close_minus_close_in_searchable_alphas()
    test_alpha_005_still_exists_for_audit()
    print("ok")
