#!/bin/zsh
set -euo pipefail

CLIENT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$CLIENT_ROOT/../.." && pwd)"
RUNTIME_DIR="$CLIENT_ROOT/.runtime"
READ_PORT="${ASTOCK_READ_SERVICE_PORT:-8011}"
READ_SERVICE_URL="${ASTOCK_READ_SERVICE_URL:-http://127.0.0.1:${READ_PORT}}"
READ_SERVICE_HEALTH="$READ_SERVICE_URL/health"
READ_SERVICE_LOG="$RUNTIME_DIR/read-service.log"

print_header() {
  printf "\n== %s ==\n" "$1"
}

service_is_up() {
  curl -fsS "$READ_SERVICE_HEALTH" >/dev/null 2>&1
}

wait_for_read_service() {
  local attempt
  for attempt in {1..35}; do
    if service_is_up; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_read_service() {
  mkdir -p "$RUNTIME_DIR"
  if service_is_up; then
    echo "Local read service is already running: $READ_SERVICE_URL"
    return 0
  fi

  print_header "Starting Python read service"
  (
    cd "$REPO_ROOT/factor_research"
    exec python3 -m uvicorn api.main:app --host 127.0.0.1 --port "$READ_PORT"
  ) >"$READ_SERVICE_LOG" 2>&1 &

  echo "$!" >"$RUNTIME_DIR/read-service.pid"

  if wait_for_read_service; then
    echo "Local read service ready: $READ_SERVICE_URL"
    return 0
  fi

  echo "Local read service did not become ready."
  echo "Log: $READ_SERVICE_LOG"
  tail -n 40 "$READ_SERVICE_LOG" || true
  return 1
}

ensure_node_deps() {
  cd "$CLIENT_ROOT"
  if [[ -d node_modules ]]; then
    return 0
  fi

  print_header "Installing desktop dependencies"
  npm install
}

ensure_electron_runtime() {
  cd "$CLIENT_ROOT"
  if npx electron --version >/dev/null 2>&1; then
    return 0
  fi

  print_header "Repairing Electron runtime"
  echo "Electron is installed as a package, but its macOS runtime binary is missing."
  echo "Trying npm rebuild electron once."

  if npm rebuild electron && npx electron --version >/dev/null 2>&1; then
    echo "Electron runtime repaired."
    return 0
  fi

  cat <<'MESSAGE'

Electron runtime is still unavailable.

Run this once from the desktop client directory if your network blocks Electron's default binary host:

  ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm rebuild electron

Then double-click AStock Lens.app again.
MESSAGE
  return 1
}

launch_desktop_client() {
  cd "$CLIENT_ROOT"
  export ASTOCK_READ_SERVICE_URL="$READ_SERVICE_URL"
  print_header "Opening AStock Lens"
  npm run dev
}

print_header "AStock Lens Local App"
echo "Client: $CLIENT_ROOT"
echo "Read service: $READ_SERVICE_URL"

start_read_service
ensure_node_deps
ensure_electron_runtime
launch_desktop_client
