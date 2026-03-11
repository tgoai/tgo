#!/usr/bin/env bash
# local-services/start: start minimum services + optional extras
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

# --- Port → service mapping ---
declare -A PORT_SERVICE
PORT_SERVICE[8000]="tgo-api"
PORT_SERVICE[8081]="tgo-ai"
PORT_SERVICE[18082]="tgo-rag"
PORT_SERVICE[8003]="tgo-platform"
PORT_SERVICE[8004]="tgo-workflow"
PORT_SERVICE[8090]="tgo-plugin-runtime"
PORT_SERVICE[8085]="tgo-device-control"
PORT_SERVICE[5173]="tgo-web"
PORT_SERVICE[5174]="tgo-widget-js"

# --- Helpers ---

is_port_open() {
  lsof -i :"$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_for_port() {
  local port="$1" label="$2" timeout="${3:-30}"
  local i=0
  printf "  Waiting for %s (:%s) " "$label" "$port"
  while ! is_port_open "$port"; do
    sleep 1
    i=$((i + 1))
    if [ "$i" -ge "$timeout" ]; then
      echo "✗ (timeout after ${timeout}s)"
      return 1
    fi
    printf "."
  done
  echo " ✓"
}

start_make_target() {
  local target="$1" port="$2" label="$3"
  if is_port_open "$port"; then
    echo "  ✓ $label already running on :$port"
    return 0
  fi
  echo "  ▶ Starting $label..."
  make "$target" > /dev/null 2>&1 &
  wait_for_port "$port" "$label" 30
}

# --- Parse args ---

EXTRAS=()
AUTO_DETECT=false
START_ALL=false

for arg in "$@"; do
  case "$arg" in
    --auto) AUTO_DETECT=true ;;
    --all)  START_ALL=true ;;
    *)      EXTRAS+=("$arg") ;;
  esac
done

# --- Auto-detect extras from git diff ---

if [ "$AUTO_DETECT" = true ]; then
  CHANGED=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only --cached)
  SERVICES=$(echo "$CHANGED" | grep '^repos/' | cut -d'/' -f2 | sort -u || true)
  for S in $SERVICES; do
    case "$S" in
      tgo-rag)            EXTRAS+=("rag") ;;
      tgo-platform)       EXTRAS+=("platform") ;;
      tgo-workflow)       EXTRAS+=("workflow") ;;
      tgo-plugin-runtime) EXTRAS+=("plugin") ;;
      tgo-device-control) EXTRAS+=("device") ;;
      tgo-web)            EXTRAS+=("web") ;;
      tgo-widget-js)     EXTRAS+=("widget") ;;
    esac
  done
fi

echo "=== Starting Local Services ==="
echo ""

# --- Step 1: Infrastructure ---

echo "▶ Infrastructure (PostgreSQL, Redis, WuKongIM)"

INFRA_UP=true
for PORT in 5432 6379 5001; do
  if ! is_port_open "$PORT"; then
    INFRA_UP=false
    break
  fi
done

if [ "$INFRA_UP" = true ]; then
  echo "  ✓ Already running"
else
  echo "  Starting..."
  make infra-up 2>&1 | grep -E '(Started|already|localhost)' | sed 's/^/  /' || true
  # Wait for PostgreSQL
  wait_for_port 5432 "PostgreSQL" 30
fi
echo ""

# --- Step 2: Migrations (if needed) ---

echo "▶ Migrations"
# Run migrations silently — they're idempotent
if make migrate > /dev/null 2>&1; then
  echo "  ✓ Migrations up to date"
else
  echo "  ⚠ Some migrations failed (non-critical if DB is already up to date)"
fi
echo ""

# --- Step 3: Minimum services ---

echo "▶ Minimum services"
start_make_target "dev-api" 8000 "tgo-api"
start_make_target "dev-ai"  8081 "tgo-ai"
echo ""

# --- Step 4: Extra services ---

if [ "$START_ALL" = true ]; then
  EXTRAS=("rag" "platform" "workflow" "plugin" "device" "web" "widget")
fi

# Deduplicate
EXTRAS=($(echo "${EXTRAS[@]}" 2>/dev/null | tr ' ' '\n' | sort -u || true))

if [ ${#EXTRAS[@]} -gt 0 ]; then
  echo "▶ Extra services"
  for EXTRA in "${EXTRAS[@]}"; do
    case "$EXTRA" in
      rag)      start_make_target "dev-rag"      18082 "tgo-rag" ;;
      platform) start_make_target "dev-platform"  8003  "tgo-platform" ;;
      workflow) start_make_target "dev-workflow"  8004  "tgo-workflow" ;;
      plugin)   start_make_target "dev-plugin"    8090  "tgo-plugin-runtime" ;;
      device)   start_make_target "dev-device"    8085  "tgo-device-control" ;;
      web)      start_make_target "dev-web"       5173  "tgo-web" ;;
      widget)   start_make_target "dev-widget"    5174  "tgo-widget-js" ;;
      *) echo "  ⚠ Unknown service: $EXTRA" ;;
    esac
  done
  echo ""
fi

# --- Summary ---

echo "=== Running Services ==="
for PORT in 8000 8081 18082 8003 8004 8090 8085 5173 5174; do
  if is_port_open "$PORT"; then
    echo "  ✓ ${PORT_SERVICE[$PORT]:-unknown} :$PORT"
  fi
done
echo ""
echo "Stop all: make stop-all"
