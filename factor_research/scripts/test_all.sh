#!/bin/bash
# Canonical one-command verification: governance guards, then every collected test.
set -e

cd "$(dirname "$0")/.."

run_guard() {
    local label="$1"
    local script="$2"
    echo "=== ${label} ==="
    python3 "${script}"
    echo ""
}

run_guard "check_layer_deps.py (分层依赖 + 台账唯一写入口)" scripts/ci/check_layer_deps.py
run_guard "check_test_discovery.py (全量测试发现:防 test_*.py 被静默排除)" scripts/ci/check_test_discovery.py
run_guard "check_control_exceptions.py (控制路径禁静默 except:pass)" scripts/ci/check_control_exceptions.py
run_guard "check_registry_evidence.py (台账9-Gate证据完整性:防照抄/跳门)" scripts/ci/check_registry_evidence.py
run_guard "check_holdout_compliance.py (自动选择路径必须 holdout 截断:§5.2 缝③)" scripts/ci/check_holdout_compliance.py
run_guard "check_no_force_promote.py (自动晋级禁 force=True/run_marginal=False:根因#1)" scripts/ci/check_no_force_promote.py
run_guard "check_no_legacy_data.py (R-DATA-001 禁代码 import/加载 data_full 旧口径)" scripts/ci/check_no_legacy_data.py
run_guard "check_naming_taxonomy.py (命名分类体系/防止模糊命名)" scripts/ci/check_naming_taxonomy.py
run_guard "check_amount_units.py (成交额单位 share×raw，禁 volume×100×price)" scripts/ci/check_amount_units.py
run_guard "check_cost_model_usage.py (正式路径禁低于 canonical 成本地板)" scripts/ci/check_cost_model_usage.py
run_guard "check_lake_writers.py (数据湖唯一写入口)" scripts/ci/check_lake_writers.py

echo "=== pytest (全部收集测试) ==="
python3 -m pytest -q

echo ""
echo "🎉 All tests passed!"
