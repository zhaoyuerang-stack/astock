#!/bin/bash
# One-command test runner for the entire project.
set -e

cd "$(dirname "$0")/.."

echo "=== check_layer_deps.py (分层依赖 + 台账唯一写入口) ==="
python3 scripts/ci/check_layer_deps.py

echo ""
echo "=== test_engine.py ==="
python3 test_engine.py

echo ""
echo "=== test_data_layer.py ==="
python3 tests/test_data_layer.py

echo ""
echo "=== test_e2e.py ==="
python3 tests/test_e2e.py

echo ""
echo "=== test_knowledge.py ==="
python3 tests/test_knowledge.py

echo ""
echo "=== test_services_phase0.py (产品 services 接缝;全量比对设 PHASE0_FULL=1) ==="
python3 tests/test_services_phase0.py

echo ""
echo "=== test_risk_phase3.py (风控控制回路;集成设 PHASE3_FULL=1) ==="
python3 tests/test_risk_phase3.py

echo ""
echo "=== test_agent_phase5.py (Agent planner + 不越权分级) ==="
python3 tests/test_agent_phase5.py

echo ""
echo "=== test_settings_phase6.py (系统设置 · 成本铁律只读 + 审计) ==="
python3 tests/test_settings_phase6.py

echo ""
echo "🎉 All tests passed!"
