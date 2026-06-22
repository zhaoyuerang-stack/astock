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
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 已知的"自动选择路径":load 全样本后据此择优/排序/打分/验证 → 必须 holdout 截断。
REQUIRED = {
    "scripts/ops/scheduled_factor_search.py": "周度因子搜索 + 9-Gate 选择",
    "portfolio/cross_asset.py": "跨资产防御腿 Δsharpe 择优",
    "workflow/promote.py": "_run_marginal 边际 ACTIVE/SHADOW 定级",
    "workflow/phase2_backtest.py": "三段回测/成本/相关性/decay 验证栈(ADR-021)",
    "workflow/phase3_wf.py": "walk-forward 训练/测试窗口(ADR-021)",
}
BOUND = re.compile(r"boundary\(|assert_search_clean|validate_on_holdout")

# ── P0-B(ADR-021):锁定 holdout.start 配置值 ──
# boundary 是软配置(settings.yaml::holdout.start),改它 = 改金库范围:原受保护的金库段
# 突然变「可搜索」,所有基于旧 boundary 的 validate_on_holdout 记录失去唯一性意义。
# 此处把当前值的 hash 钉死;任何改动让守卫 exit 1,强制走 DECISIONS(ADR)+ 更新本 pin。
SETTINGS_YAML = ROOT / "app_config" / "settings.yaml"
EXPECTED_BOUNDARY = "2025-01-01"
EXPECTED_BOUNDARY_HASH = "14973c591b26d5116b3ce3508c60adfe345a1201723a45f18dacc0293da2ec7a"


def check_boundary_lock() -> list[tuple[str, str]]:
    """holdout.start 必须 == 钉死值,否则违规(改金库须 ADR + 更新本 pin)。"""
    try:
        import yaml
        cfg = yaml.safe_load(SETTINGS_YAML.read_text(encoding="utf-8")) or {}
        start = str((cfg.get("holdout") or {}).get("start", ""))
    except Exception as exc:  # noqa: BLE001 — 读不到配置即视为违规,不静默
        return [("app_config/settings.yaml", f"无法读取 holdout.start: {exc}")]
    h = hashlib.sha256(start.encode()).hexdigest()
    if h != EXPECTED_BOUNDARY_HASH:
        return [(
            "app_config/settings.yaml::holdout.start",
            f"金库边界被改动:当前 {start!r}(hash {h[:12]})≠ 钉死 {EXPECTED_BOUNDARY!r}"
            f"(hash {EXPECTED_BOUNDARY_HASH[:12]})。改金库 = 改唯一性语义,须先记 DECISIONS(ADR)"
            f"并同步更新 check_holdout_compliance.py 的 EXPECTED_BOUNDARY[_HASH]。",
        )]
    return []


def main() -> int:
    violations = []
    violations.extend(check_boundary_lock())  # P0-B:金库边界配置锁
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
