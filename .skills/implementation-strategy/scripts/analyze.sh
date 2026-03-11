#!/usr/bin/env bash
# implementation-strategy: analyze change impact across services
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

# Accept file args or use git diff
if [ $# -gt 0 ]; then
  CHANGED_FILES="$*"
else
  CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only --cached)
fi

if [ -z "$CHANGED_FILES" ]; then
  echo "No files to analyze. Pass files as arguments or stage changes."
  exit 0
fi

echo "=== Implementation Strategy Analysis ==="
echo ""

# Extract services
SERVICES=$(echo "$CHANGED_FILES" | tr ' ' '\n' | grep '^repos/' | cut -d'/' -f2 | sort -u)

echo "## Affected Services"
for S in $SERVICES; do
  echo "  - $S"
done

echo ""
echo "## Dependency Map"
echo ""

# Define dependency relationships
declare -A DEPS
DEPS[tgo-web]="→ tgo-api (HTTP)"
DEPS[tgo-widget-js]="→ tgo-api (HTTP)"
DEPS[tgo-widget-miniprogram]="→ tgo-api (HTTP)"
DEPS[tgo-api]="→ tgo-ai, tgo-rag, tgo-platform, tgo-workflow, tgo-plugin-runtime, tgo-device-control (HTTP)"
DEPS[tgo-ai]="→ tgo-plugin-runtime (HTTP); ← tgo-api (called by)"
DEPS[tgo-rag]="← tgo-api (called by)"
DEPS[tgo-platform]="→ tgo-api (HTTP); ← external platforms (webhooks)"
DEPS[tgo-workflow]="← tgo-api (called by)"
DEPS[tgo-plugin-runtime]="← tgo-ai (called by)"
DEPS[tgo-device-control]="← tgo-api, tgo-device-agent (called by)"
DEPS[tgo-device-agent]="→ tgo-device-control (TCP JSON-RPC)"

for S in $SERVICES; do
  if [ -n "${DEPS[$S]:-}" ]; then
    echo "  $S ${DEPS[$S]}"
  else
    echo "  $S (standalone)"
  fi
done

echo ""
echo "## Sync Checklist"

# Check for schema/type changes
SCHEMA_CHANGES=$(echo "$CHANGED_FILES" | tr ' ' '\n' | grep -E '(schemas/|types/|models/)' || true)
if [ -n "$SCHEMA_CHANGES" ]; then
  echo "  ⚠ Schema/type changes detected — check upstream & downstream consumers:"
  echo "$SCHEMA_CHANGES" | sed 's/^/    /'
fi

# Check for API route changes
API_CHANGES=$(echo "$CHANGED_FILES" | tr ' ' '\n' | grep -E '(api/|routes\.|router)' || true)
if [ -n "$API_CHANGES" ]; then
  echo "  ⚠ API route changes detected — verify client compatibility:"
  echo "$API_CHANGES" | sed 's/^/    /'
fi

# Check for streaming changes
STREAM_CHANGES=$(echo "$CHANGED_FILES" | tr ' ' '\n' | grep -iE '(stream|sse|wukongim|json.?render)' || true)
if [ -n "$STREAM_CHANGES" ]; then
  echo "  ⚠ Streaming/IM changes detected — verify all consumers:"
  echo "$STREAM_CHANGES" | sed 's/^/    /'
fi

echo ""
echo "=== End Analysis ==="
