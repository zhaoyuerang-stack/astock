"""控制路径静默异常守卫(Task 17)。

控制路径(准入/裁决/信号/执行/可用性)里的 `except: pass` / `except Exception: pass`
会把异常悄悄吞成「通过」——这是防自欺体系最危险的漏洞。本守卫 AST 扫描下列路径,
禁止 handler 体仅为 pass / ...(纯吞)。允许的处理必须有动作(log / raise / 返回失败态)。

只读 AST,违规 exit 1。检测函数吃源码字符串,便于 fixture 测试。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 控制路径清单(新增控制模块须加入)
CONTROL_PATHS = [
    "core/analysis/nine_gates.py",
    "core/analysis/nine_gate_policy.py",
    "services/read/trade_readiness.py",
    "governance/holdout.py",
    "runtime/production_readiness.py",
    "runtime/deployment.py",
    "workflow/admission.py",
    "workflow/promote.py",
    "workflow/phase4_register.py",
    "governance/state_machine.py",
    "governance/control_events.py",
    "portfolio/paper_engine.py",
    "portfolio/paper_accounts.py",
]


def _body_is_silent(handler: ast.ExceptHandler) -> bool:
    """handler 体是否纯吞:仅 pass,或仅 `...`(Ellipsis 常量),无任何动作。"""
    body = [n for n in handler.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                                            and isinstance(n.value.value, str))]  # 去掉 docstring
    if len(body) != 1:
        return False
    only = body[0]
    if isinstance(only, ast.Pass):
        return True
    if isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant) and only.value.value is Ellipsis:
        return True
    return False


def scan_source(src: str, label: str = "") -> list[str]:
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"[{label}] 语法错误,无法扫描: {e}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _body_is_silent(node):
            out.append(f"[{label}:L{node.lineno}] 控制路径静默吞异常(except: pass)"
                       f"—— 必须 log / raise / 返回 UNKNOWN|FAILED_TO_RUN|BLOCKED,不得转成通过")
    return out


def main() -> int:
    violations = []
    for rel in CONTROL_PATHS:
        p = ROOT / rel
        if not p.exists():
            continue
        violations += scan_source(p.read_text(encoding="utf-8"), label=rel)
    if violations:
        print("❌ 控制路径静默异常守卫失败:")
        for v in violations:
            print("  " + v)
        return 1
    print(f"✅ 控制路径静默异常守卫通过(扫描 {len(CONTROL_PATHS)} 个控制模块,无 except:pass)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
