#!/usr/bin/env bash
# code-change-verification: detect changed services and run verification
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

# Get changed files (staged + unstaged vs HEAD)
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only)
if [ -z "$CHANGED_FILES" ]; then
  CHANGED_FILES=$(git diff --name-only --cached)
fi

if [ -z "$CHANGED_FILES" ]; then
  echo "✓ No changed files detected"
  exit 0
fi

# Extract unique service directories
SERVICES=$(echo "$CHANGED_FILES" | grep '^repos/' | cut -d'/' -f2 | sort -u)

if [ -z "$SERVICES" ]; then
  echo "✓ No service code changes detected"
  exit 0
fi

echo "Changed services: $SERVICES"
echo "---"

FAILED=0

for SERVICE in $SERVICES; do
  SERVICE_DIR="repos/$SERVICE"
  if [ ! -d "$SERVICE_DIR" ]; then
    continue
  fi

  echo ""
  echo "▶ Verifying $SERVICE..."

  case "$SERVICE" in
    tgo-web)
      cd "$REPO_ROOT/$SERVICE_DIR"
      if yarn type-check && yarn lint && yarn build; then
        echo "  ✓ $SERVICE passed"
      else
        echo "  ✗ $SERVICE FAILED"
        FAILED=1
      fi
      cd "$REPO_ROOT"
      ;;

    tgo-widget-js)
      cd "$REPO_ROOT/$SERVICE_DIR"
      if npm run build; then
        echo "  ✓ $SERVICE passed"
      else
        echo "  ✗ $SERVICE FAILED"
        FAILED=1
      fi
      cd "$REPO_ROOT"
      ;;

    tgo-device-agent)
      cd "$REPO_ROOT/$SERVICE_DIR"
      if go vet ./...; then
        echo "  ✓ $SERVICE passed"
      else
        echo "  ✗ $SERVICE FAILED"
        FAILED=1
      fi
      cd "$REPO_ROOT"
      ;;

    tgo-widget-miniprogram)
      cd "$REPO_ROOT/$SERVICE_DIR"
      if npm run build; then
        echo "  ✓ $SERVICE passed"
      else
        echo "  ✗ $SERVICE FAILED"
        FAILED=1
      fi
      cd "$REPO_ROOT"
      ;;

    tgo-cli|tgo-widget-cli)
      cd "$REPO_ROOT/$SERVICE_DIR"
      if npm run build; then
        echo "  ✓ $SERVICE passed"
      else
        echo "  ✗ $SERVICE FAILED"
        FAILED=1
      fi
      cd "$REPO_ROOT"
      ;;

    tgo-ai|tgo-api|tgo-rag|tgo-platform|tgo-workflow|tgo-plugin-runtime|tgo-device-control)
      cd "$REPO_ROOT/$SERVICE_DIR"
      if [ -f "pyproject.toml" ]; then
        # Determine source directory
        SRC_DIR="app"
        if [ -d "src" ]; then
          SRC_DIR="src"
        fi

        CMDS_OK=true
        if poetry run mypy "$SRC_DIR" 2>/dev/null; then
          echo "  ✓ mypy passed"
        else
          echo "  ✗ mypy failed"
          CMDS_OK=false
        fi

        if poetry run flake8 "$SRC_DIR" 2>/dev/null; then
          echo "  ✓ flake8 passed"
        else
          # Try ruff as fallback (tgo-platform uses ruff)
          if poetry run ruff check . 2>/dev/null; then
            echo "  ✓ ruff passed"
          else
            echo "  ✗ lint failed"
            CMDS_OK=false
          fi
        fi

        if [ "$CMDS_OK" = true ]; then
          echo "  ✓ $SERVICE passed"
        else
          echo "  ✗ $SERVICE FAILED"
          FAILED=1
        fi
      fi
      cd "$REPO_ROOT"
      ;;

    *)
      echo "  ⚠ No verification configured for $SERVICE"
      ;;
  esac
done

echo ""
echo "---"
if [ "$FAILED" -eq 0 ]; then
  echo "✓ All verifications passed"
else
  echo "✗ Some verifications FAILED"
  exit 1
fi
