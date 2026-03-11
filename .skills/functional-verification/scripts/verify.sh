#!/usr/bin/env bash
# functional-verification: use tgo-cli and tgo-widget-cli to verify API changes at runtime
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

TGO_CLI="node repos/tgo-cli/dist/index.js"
WIDGET_CLI="node repos/tgo-widget-cli/dist/index.js"

# --- Helpers ---

PASSED=0
FAILED=0
SKIPPED=0

run_check() {
  local label="$1"
  shift
  printf "  %-50s" "$label"
  if OUTPUT=$("$@" 2>&1); then
    echo "✓"
    PASSED=$((PASSED + 1))
  else
    echo "✗"
    echo "    $OUTPUT" | head -3
    FAILED=$((FAILED + 1))
  fi
}

skip_check() {
  local label="$1"
  local reason="$2"
  printf "  %-50s⊘ %s\n" "$label" "$reason"
  SKIPPED=$((SKIPPED + 1))
}

# --- Preflight ---

echo "=== Functional Verification ==="
echo ""

# Check CLI builds
TGO_CLI_OK=true
WIDGET_CLI_OK=true

if [ ! -f "repos/tgo-cli/dist/index.js" ]; then
  echo "⚠ tgo-cli not built. Run: cd repos/tgo-cli && npm run build"
  TGO_CLI_OK=false
fi

if [ ! -f "repos/tgo-widget-cli/dist/index.js" ]; then
  echo "⚠ tgo-widget-cli not built. Run: cd repos/tgo-widget-cli && npm run build"
  WIDGET_CLI_OK=false
fi

# Check CLI configs
TGO_CONFIGURED=true
WIDGET_CONFIGURED=true

if [ ! -f "$HOME/.tgo/config.json" ]; then
  echo "⚠ tgo-cli not configured. Run: $TGO_CLI auth login -u <user> -p <pass>"
  TGO_CONFIGURED=false
fi

if [ ! -f "$HOME/.tgo-widget/config.json" ]; then
  echo "⚠ tgo-widget-cli not configured. Run: $WIDGET_CLI init --api-key <key> --server <url>"
  WIDGET_CONFIGURED=false
fi

# Check server reachability
TGO_SERVER=$(node -e "try{console.log(JSON.parse(require('fs').readFileSync('$HOME/.tgo/config.json','utf8')).server||'')}catch{console.log('')}" 2>/dev/null || echo "")
SERVER_UP=false

if [ -n "$TGO_SERVER" ]; then
  if curl -sf "${TGO_SERVER}/api/v1/health" >/dev/null 2>&1 || curl -sf "${TGO_SERVER}/health" >/dev/null 2>&1; then
    SERVER_UP=true
    echo "✓ Server reachable at $TGO_SERVER"
  else
    echo "⚠ Server not reachable at $TGO_SERVER — start with: make dev-all"
  fi
fi

if [ "$TGO_CLI_OK" = false ] && [ "$WIDGET_CLI_OK" = false ]; then
  echo "✗ No CLIs available. Build them first."
  exit 1
fi

if [ "$SERVER_UP" = false ]; then
  echo "✗ Server not running. Start services first."
  exit 1
fi

echo ""

# --- Determine what to verify ---

RUN_ALL=false
TARGET_SERVICE=""

if [ "${1:-}" = "--all" ]; then
  RUN_ALL=true
elif [ -n "${1:-}" ]; then
  TARGET_SERVICE="$1"
else
  # Auto-detect from git diff
  CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only --cached)
  TARGET_SERVICES=$(echo "$CHANGED_FILES" | grep '^repos/' | cut -d'/' -f2 | sort -u || true)
fi

should_verify() {
  local service="$1"
  if [ "$RUN_ALL" = true ]; then return 0; fi
  if [ -n "$TARGET_SERVICE" ]; then
    [ "$TARGET_SERVICE" = "$service" ] && return 0 || return 1
  fi
  echo "$TARGET_SERVICES" | grep -q "^${service}$" 2>/dev/null && return 0 || return 1
}

# --- Staff-side checks (tgo-cli) ---

if [ "$TGO_CLI_OK" = true ] && [ "$TGO_CONFIGURED" = true ]; then

  # System / API gateway
  if should_verify "tgo-api" || [ "$RUN_ALL" = true ]; then
    echo "▶ tgo-api (staff-side)"
    run_check "system info" $TGO_CLI system info -o json
    run_check "auth whoami" $TGO_CLI auth whoami -o json
    run_check "conversation list" $TGO_CLI conversation list --limit 1 -o json
    run_check "visitor list" $TGO_CLI visitor list --limit 1 -o json
    run_check "staff list" $TGO_CLI staff list --limit 1 -o json
    echo ""
  fi

  # AI service
  if should_verify "tgo-ai" || [ "$RUN_ALL" = true ]; then
    echo "▶ tgo-ai (staff-side)"
    run_check "agent list" $TGO_CLI agent list --limit 1 -o json
    run_check "provider list" $TGO_CLI provider list -o json
    run_check "chat team (e2e)" $TGO_CLI chat team --message "respond with just: ok" -o json
    echo ""
  fi

  # RAG service
  if should_verify "tgo-rag" || [ "$RUN_ALL" = true ]; then
    echo "▶ tgo-rag (staff-side)"
    run_check "knowledge list" $TGO_CLI knowledge list --limit 1 -o json
    echo ""
  fi

  # Workflow service
  if should_verify "tgo-workflow" || [ "$RUN_ALL" = true ]; then
    echo "▶ tgo-workflow (staff-side)"
    run_check "workflow list" $TGO_CLI workflow list --limit 1 -o json
    echo ""
  fi

  # Platform service
  if should_verify "tgo-platform" || [ "$RUN_ALL" = true ]; then
    echo "▶ tgo-platform (staff-side)"
    run_check "platform list" $TGO_CLI platform list -o json
    echo ""
  fi

else
  skip_check "staff-side checks" "tgo-cli not available or not configured"
  echo ""
fi

# --- Visitor-side checks (tgo-widget-cli) ---

if [ "$WIDGET_CLI_OK" = true ] && [ "$WIDGET_CONFIGURED" = true ]; then

  VISITOR_RELEVANT=false
  if should_verify "tgo-api" || should_verify "tgo-ai" || should_verify "tgo-widget-js" || should_verify "tgo-widget-miniprogram" || should_verify "tgo-platform" || [ "$RUN_ALL" = true ]; then
    VISITOR_RELEVANT=true
  fi

  if [ "$VISITOR_RELEVANT" = true ]; then
    echo "▶ Visitor-side"
    run_check "platform info" $WIDGET_CLI platform info -o json
    run_check "channel info" $WIDGET_CLI channel info -o json
    run_check "chat history" $WIDGET_CLI chat history --limit 3 -o json
    run_check "chat send (e2e, no-stream)" $WIDGET_CLI chat send --message "respond with just: ok" --no-stream -o json
    echo ""
  fi

else
  if should_verify "tgo-api" || should_verify "tgo-widget-js" || [ "$RUN_ALL" = true ]; then
    skip_check "visitor-side checks" "tgo-widget-cli not available or not configured"
    echo ""
  fi
fi

# --- Summary ---

echo "=== Summary ==="
TOTAL=$((PASSED + FAILED + SKIPPED))
echo "  Passed:  $PASSED"
echo "  Failed:  $FAILED"
echo "  Skipped: $SKIPPED"
echo "  Total:   $TOTAL"

if [ "$FAILED" -gt 0 ]; then
  echo ""
  echo "✗ Some checks FAILED"
  exit 1
else
  echo ""
  echo "✓ All checks passed"
fi
