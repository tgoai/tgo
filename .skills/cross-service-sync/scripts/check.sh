#!/usr/bin/env bash
# cross-service-sync: check cross-service type/schema consistency
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only --cached)
if [ -z "$CHANGED_FILES" ]; then
  echo "✓ No changes detected"
  exit 0
fi

# Find schema/type changes
SCHEMA_FILES=$(echo "$CHANGED_FILES" | grep -E '(schemas/|types/|interfaces/)' || true)

if [ -z "$SCHEMA_FILES" ]; then
  echo "✓ No schema/type changes detected"
  exit 0
fi

echo "Schema/type changes detected:"
echo "$SCHEMA_FILES" | sed 's/^/  /'
echo ""

# Extract the service that owns the change
CHANGED_SERVICES=$(echo "$SCHEMA_FILES" | grep '^repos/' | cut -d'/' -f2 | sort -u)

# Extract changed identifiers from diff
echo "## Searching for cross-service references..."
echo ""

for FILE in $SCHEMA_FILES; do
  if [ ! -f "$FILE" ]; then
    continue
  fi

  # Get added/modified class/type names from diff
  IDENTIFIERS=$(git diff HEAD -- "$FILE" 2>/dev/null | grep '^+' | grep -oE '(class|interface|type|enum)\s+\w+' | awk '{print $2}' | sort -u || true)

  if [ -z "$IDENTIFIERS" ]; then
    continue
  fi

  SOURCE_SERVICE=$(echo "$FILE" | cut -d'/' -f2)

  for ID in $IDENTIFIERS; do
    echo "▶ Searching for '$ID' references outside $SOURCE_SERVICE..."
    REFS=$(grep -rl "$ID" repos/ --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" 2>/dev/null | grep -v "repos/$SOURCE_SERVICE/" | grep -v "node_modules" | grep -v "__pycache__" | head -20 || true)
    if [ -n "$REFS" ]; then
      echo "  ⚠ Found references that may need updating:"
      echo "$REFS" | sed 's/^/    /'
    fi
  done
done

echo ""
echo "## Service Dependency Quick Reference"
echo "  tgo-api ↔ tgo-ai: chat schemas, tool schemas"
echo "  tgo-api ↔ tgo-web: all API response types"
echo "  tgo-api ↔ tgo-widget-js: visitor/chat message types"
echo "  tgo-ai ↔ tgo-plugin-runtime: tool call/result schemas"
echo "  tgo-device-control ↔ tgo-device-agent: JSON-RPC protocol"
echo "  tgo-widget-js ↔ tgo-widget-miniprogram: json-render types"
