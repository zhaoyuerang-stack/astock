#!/bin/bash
# One-command test runner for the entire project.
set -e

cd "$(dirname "$0")/.."

echo "=== test_engine.py ==="
python3 test_engine.py

echo ""
echo "=== test_data_layer.py ==="
python3 tests/test_data_layer.py

echo ""
echo "=== test_e2e.py ==="
python3 tests/test_e2e.py

echo ""
echo "🎉 All tests passed!"
