"""Holdout 合规守卫——自动选择路径必须把择优数据截到 <boundary(LOOP_ENGINEERING §5.2)。

背景(§5.2 缝③):holdout 边界此前靠各脚本手工加,默认就漏——全仓 80+ 处 load 全样本,
只有少数截断。任何**在自动环里 load 全样本并据此择优/排序/边际定级**的路径,若不截到
<boundary,就是"loop 偷看金库" = 工业化自欺。本守卫锁定已知的自动选择路径:每个必须引用
boundary() / assert_search_clean / validate_on_holdout 之一。

新增自动选择路径(load 全样本 + 排序/择优/边际定级)时:① 把择优数据截到 <boundary;
② 把文件加进 REQUIRED。纯监控/报表/实盘信号(decay_monitor/tradability/dashboard/
paper_trade/live_readiness)合法使用全/近期数据,**不是选择**,不在此列。
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 已知的"自动选择路径":load 全样本后据此择优/排序/打分 → 必须 holdout 截断。
REQUIRED = {
    "scripts/ops/scheduled_factor_search.py": "周度因子搜索 + 9-Gate 选择",
    "portfolio/cross_asset.py": "跨资产防御腿 Δsharpe 择优",
    "workflow/promote.py": "_run_marginal 边际 ACTIVE/SHADOW 定级",
}
BOUND = re.compile(r"boundary\(|assert_search_clean|validate_on_holdout")


def main() -> int:
    violations = []
    for rel, why in REQUIRED.items():
        p = ROOT / rel
        if not p.exists():
            violations.append((rel, "文件不存在(REQUIRED 名单过期?)"))
            continue
        if not BOUND.search(p.read_text(encoding="utf-8")):
            violations.append((rel, f"自动选择路径({why})未引用 holdout 截断 → §5.2 缝③ 泄露"))
    scheduled = (ROOT / "scripts/ops/scheduled_factor_search.py").read_text(encoding="utf-8")
    if "review_queue.all()" in scheduled:
        violations.append((
            "scripts/ops/scheduled_factor_search.py",
            "自动审计不得遍历 ReviewQueue.all();只能处理本轮新增 pending",
        ))
    for path in ROOT.rglob("*.py"):
        if any(part in {"data_lake", "scratch", "__pycache__"} for part in path.parts):
            continue
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "validate_on_holdout(" not in text or path.name in {"holdout.py", "check_holdout_compliance.py"}:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            if name != "validate_on_holdout":
                continue
            keywords = {kw.arg for kw in node.keywords}
            if "spec_hash" not in keywords or "data_fingerprint" not in keywords:
                violations.append((
                    str(path.relative_to(ROOT)),
                    "validate_on_holdout 调用缺 spec_hash/data_fingerprint 身份",
                ))
                break
    if violations:
        print("🚨 Holdout 合规违规(自动选择路径必须截到 <boundary,见 LOOP_ENGINEERING §5.2):")
        for rel, msg in violations:
            print(f"  - {rel}: {msg}")
        return 1
    print(f"Holdout 合规检查通过({len(REQUIRED)} 个自动选择路径均已 holdout 截断)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
