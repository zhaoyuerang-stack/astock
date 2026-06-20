"""数据湖唯一写入口守卫——湖核心区只允许数据层模块写入。

背景(2026-06-12 事故):ad-hoc 修复脚本直写 daily_all 且不更新 manifest,
造成数据与台账失联;类比策略侧"台账唯一写入口 = strategy_registry"铁律,
数据侧同样需要:**写 data_lake 核心区(price/fundamental/meta/capital)的
代码必须住在 lake/ 或 scripts/data/(含 scripts/repair/ 修复工具)**。

静态检查:凡 to_parquet 且引用湖核心路径、又不在允许目录的文件 → 违规。
LEGACY 名单是显式记录的迁移欠债,新增违规直接报错。
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_PREFIXES = ("lake/", "scripts/data/", "scripts/repair/", "tests/")
# 历史欠债名单。必须保持为空;新增违规不允许用白名单掩盖。
LEGACY = set()
LAKE_CORE = re.compile(r"data_lake[/\"']\s*(?:/\s*)?(?:price|fundamental|meta|capital)|data_lake/(?:price|fundamental|meta|capital)")


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
        if "to_parquet" in text and LAKE_CORE.search(text):
            violations.append(rel)

    if violations:
        print("🚨 数据湖唯一写入口违规(写湖核心区的代码必须在 lake/ 或 scripts/data/):")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(f"数据湖写入口检查通过({len(files)} 个文件,legacy 豁免 {len(LEGACY)} 个)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
