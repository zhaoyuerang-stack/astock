#!/bin/zsh
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/dev_serve.sh api
  scripts/ops/dev_serve.sh web

Environment:
  API_PORT=8011
  API_HOST=127.0.0.1
  WEB_PORT=3000
  WEB_HOST=127.0.0.1
  NEXT_PUBLIC_API_BASE=http://127.0.0.1:8011
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${0:a}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
FACTOR_ROOT="$PROJECT_ROOT/factor_research"
WEB_ROOT="$PROJECT_ROOT/web"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8011}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-3000}"
NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_BASE:-http://127.0.0.1:${API_PORT}}"

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

case "$1" in
  api)
    cd "$FACTOR_ROOT"
    exec python3 -m uvicorn api.main:app --host "$API_HOST" --port "$API_PORT" --reload
    ;;
  web)
    cd "$WEB_ROOT"
    NEXT_PUBLIC_API_BASE="$NEXT_PUBLIC_API_BASE" exec npm run dev -- --hostname "$WEB_HOST" --port "$WEB_PORT"
    ;;
  *)
    usage
    exit 2
    ;;
esac
