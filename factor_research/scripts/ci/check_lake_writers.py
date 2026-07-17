"""数据湖唯一写入口守卫——湖区只允许数据层模块写入。

背景(2026-06-12 事故):ad-hoc 修复脚本直写 daily_all 且不更新 manifest,
造成数据与台账失联;类比策略侧"台账唯一写入口 = strategy_registry"铁律,
数据侧同样需要:**写 data_lake 任意子目录的代码必须住在 lake/ 或
scripts/data/(含 scripts/repair/ 修复工具)**。

静态检查(守卫审计 #4,2026-07-17 扩面):
  - 路径:匹配 data_lake/<任意子目录> 字面量,或 Path 组件 `"data_lake"`
    (不再白名单枚举 price|fundamental|meta|capital 四目录)
  - 写动词:{to_parquet, to_csv, to_pickle, write_table}
  - 文件枚举:磁盘 rglob(未跟踪脚本不再隐身);排除 data_lake/、__pycache__、
    .pytest_cache;tests/ 与 scripts/ci/ 豁免
  - 判定粒度仍为**文件级共现**(写动词 + 湖路径同文件)——与扩面前一致,
    不升 AST 级(防即兴设计)

存量命中进 PENDING_REMEDIATION(响而不阻),新增即红。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_PREFIXES = ("lake/", "scripts/data/", "scripts/repair/", "tests/", "scripts/ci/")
WRITE_VERBS = re.compile(r"\b(to_parquet|to_csv|to_pickle|write_table)\b")
# data_lake/<任意子目录> 字面量,或 Path 组件 'data_lake' / "data_lake"
LAKE_REF = re.compile(r"""data_lake/\w+|['\"]data_lake['\"]""")

# 存量欠债(审计 #4 扩面后扫出)。响而不阻;真写湖者应改走 lake/ canonical writer。
# 审计 #5:promote_composite / run_nine_gates_all 已迁 write_version_returns,从 PENDING 销账;
# 此后任何直写 version_returns 即硬红(新违规不在基线)。
PENDING_REMEDIATION: dict[str, str] = {
    # ── 真写湖(迁移欠债:应改走 lake/ canonical writer)──
    "factor_store/store.py":
        "迁移欠债:to_parquet 写 data_lake/factor_store;应改走 lake/ 或登记为 canonical 区",
    "factors/autoresearch_dsl.py":
        "迁移欠债:to_parquet 写 data_lake/factor_store/panels 缓存",
    # ── 文件级共现启发式命中(读湖 + to_csv 到 OUT/非湖路径;非真写湖,待 AST 精化)──
    "scripts/research/build_largecap_value_quality.py":
        "文件级共现:读 data_lake + to_csv 到 OUT(非真写湖)",
    "scripts/research/build_quality_growth.py":
        "文件级共现:读 data_lake + to_csv 到 OUT(非真写湖)",
    "scripts/research/fundamental_midcap.py":
        "文件级共现:读 data_lake + to_csv 到 OUT(非真写湖)",
    "scripts/research/northbound_factor.py":
        "文件级共现:读 data_lake + to_csv 到 OUT(非真写湖)",
    "scripts/research/archive/hmm_exit_smallcap.py":
        "文件级共现:注释/读路径含 data_lake + to_csv 到结果目录",
    "scripts/research/archive/hmm_stress_guard_smallcap.py":
        "文件级共现:注释/读路径含 data_lake + to_csv 到结果目录",
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


def file_is_violation(text: str) -> bool:
    """文件级共现:含写动词且含湖路径引用。"""
    return bool(WRITE_VERBS.search(text) and LAKE_REF.search(text))


def scan(root: Path | None = None) -> list[str]:
    """返回全部共现命中(含 PENDING 候选),供测试断言。"""
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
        if file_is_violation(text):
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
