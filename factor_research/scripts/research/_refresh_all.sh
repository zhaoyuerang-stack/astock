#!/bin/bash
# 一次性刷新:逐版本重跑 9-Gate(采集收益+落 2A 字段)→ lineage_pbo(2B/2C)。
# 顺序执行,避免并发写 strategy_versions.json 损坏。
set -u
cd "$(dirname "$0")/../.." || exit 1

run() {  # family_strategy_name  version
  echo ">>> [$(date +%H:%M:%S)] 9-Gate $1/$2"
  python3 scripts/research/run_nine_gates_all.py --strategy "$1" --version "$2" --persist 2>&1 \
    | grep -E "persist|REJECTED|APPROVED|FAIL|Error|Traceback" | head -8
}

# 11 个在册版本(CLI 支持的 5 个家族)
run illiquidity v1.0
run illiquidity v1.1
run illiquidity v1.3
run illiquidity v3.1
run hq_momentum v1.0
run hq_momentum v1.0-full
run large_cap v1.0
run large_cap v1.1
run large_cap v1.1-full
run size_earnings v1.0
run small_cap v2.0

echo ">>> [$(date +%H:%M:%S)] lineage_pbo (2B/2C)"
python3 scripts/research/lineage_pbo.py 2>&1 | tail -40
echo ">>> [$(date +%H:%M:%S)] ALL DONE"
