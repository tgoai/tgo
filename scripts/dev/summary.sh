#!/bin/bash
# Print a dev-ready access summary for the currently running Compose services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-.env.dev}"

if [ ! -f "$PROJECT_ROOT/$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$PROJECT_ROOT/$ENV_FILE"
set +a

normalize_services() {
  printf '%s\n' "$1" | tr ' ' '\n' | sed '/^$/d' | sort -u
}

load_running_services() {
  if [ -n "${RUNNING_SERVICES:-}" ]; then
    normalize_services "$RUNNING_SERVICES"
    return 0
  fi

  local -a profile_flags
  profile_flags=()

  if [ -n "${PROFILES:-}" ]; then
    local profile
    IFS=',' read -ra raw_profiles <<< "$PROFILES"
    for profile in "${raw_profiles[@]}"; do
      profile="${profile// /}"
      if [ -n "$profile" ]; then
        profile_flags+=(--profile "$profile")
      fi
    done
  fi

  (
    cd "$PROJECT_ROOT"
    if [ "${#profile_flags[@]}" -gt 0 ]; then
      docker compose \
        --env-file "$ENV_FILE" \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        "${profile_flags[@]}" \
        ps --services --status running
    else
      docker compose \
        --env-file "$ENV_FILE" \
        -f docker-compose.yml \
        -f docker-compose.dev.yml \
        ps --services --status running
    fi
  )
}

service_is_running() {
  local service="$1"
  printf '%s\n' "$RUNNING_SERVICES_LIST" | grep -qx "$service"
}

add_line() {
  local var_name="$1"
  local line="$2"
  printf -v "$var_name" '%s- %s\n' "${!var_name}" "$line"
}

print_section() {
  local title="$1"
  local lines="$2"

  if [ -z "$lines" ]; then
    return 0
  fi

  printf '%s\n' "$title"
  printf '%s' "$lines"
  printf '\n'
}

RUNNING_SERVICES_LIST="$(load_running_services)"

POSTGRES_HOST_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB_NAME="${POSTGRES_DB:-tgo}"
POSTGRES_USERNAME="${POSTGRES_USER:-tgo}"
POSTGRES_SECRET="${POSTGRES_PASSWORD:-tgo}"
REDIS_HOST_PORT="${REDIS_PORT:-6379}"
API_PORT="${TGO_API_PORT:-8000}"
AI_PORT="${TGO_AI_PORT:-8081}"
RAG_PORT="${TGO_RAG_PORT:-18082}"
PLATFORM_PORT="${TGO_PLATFORM_PORT:-8003}"
WORKFLOW_PORT="${TGO_WORKFLOW_PORT:-8004}"
PLUGIN_RUNTIME_PORT="${TGO_PLUGIN_RUNTIME_PORT:-8090}"
DEVICE_CONTROL_PORT="${TGO_DEVICE_CONTROL_PORT:-8085}"
WEB_PORT="${TGO_WEB_PORT:-5173}"
WIDGET_PORT="${TGO_WIDGET_PORT:-5174}"
FLOWER_PORT_VALUE="${FLOWER_PORT:-5555}"
ADMINER_PORT_VALUE="${ADMINER_PORT:-8089}"
AGENTOS_PORT_VALUE="${AGENTOS_PORT:-7778}"
WUKONGIM_HTTP_URL="http://localhost:5001"
WUKONGIM_WS_URL="${WK_EXTERNAL_WSADDR:-localhost:5200}"

case "$WUKONGIM_WS_URL" in
  ws://*|wss://*) ;;
  *) WUKONGIM_WS_URL="ws://$WUKONGIM_WS_URL" ;;
esac

WEB_SECTION=""
API_SECTION=""
INFRA_SECTION=""
TOOLS_SECTION=""

if service_is_running tgo-web; then
  add_line WEB_SECTION "Admin console: http://localhost:${WEB_PORT}"
fi

if service_is_running tgo-widget-js; then
  add_line WEB_SECTION "Widget preview: ${VITE_WIDGET_DEMO_URL:-http://localhost:${WIDGET_PORT}/demo.html}"
  add_line WEB_SECTION "Widget SDK: ${VITE_WIDGET_SCRIPT_BASE:-http://localhost:${WIDGET_PORT}/tgo-widget-sdk.js}"
fi

if service_is_running tgo-api; then
  add_line API_SECTION "API: http://localhost:${API_PORT} (docs: http://localhost:${API_PORT}/docs, health: http://localhost:${API_PORT}/health)"
fi

if service_is_running tgo-ai; then
  add_line API_SECTION "AI: http://localhost:${AI_PORT} (health: http://localhost:${AI_PORT}/health)"
fi

if service_is_running tgo-rag; then
  add_line API_SECTION "RAG: http://localhost:${RAG_PORT} (health: http://localhost:${RAG_PORT}/health)"
fi

if service_is_running tgo-platform; then
  add_line API_SECTION "Platform: http://localhost:${PLATFORM_PORT} (health: http://localhost:${PLATFORM_PORT}/health)"
fi

if service_is_running tgo-workflow; then
  add_line API_SECTION "Workflow: http://localhost:${WORKFLOW_PORT} (health: http://localhost:${WORKFLOW_PORT}/health)"
fi

if service_is_running tgo-plugin-runtime; then
  add_line API_SECTION "Plugin Runtime: http://localhost:${PLUGIN_RUNTIME_PORT} (health: http://localhost:${PLUGIN_RUNTIME_PORT}/health)"
fi

if service_is_running tgo-device-control; then
  add_line API_SECTION "Device Control: http://localhost:${DEVICE_CONTROL_PORT} (health: http://localhost:${DEVICE_CONTROL_PORT}/health)"
fi

if service_is_running postgres; then
  add_line INFRA_SECTION "Postgres: postgresql://${POSTGRES_USERNAME}:${POSTGRES_SECRET}@localhost:${POSTGRES_HOST_PORT}/${POSTGRES_DB_NAME} (db=${POSTGRES_DB_NAME}, user=${POSTGRES_USERNAME}, password=${POSTGRES_SECRET})"
fi

if service_is_running redis; then
  add_line INFRA_SECTION "Redis: redis://localhost:${REDIS_HOST_PORT}/0"
fi

if service_is_running wukongim; then
  add_line INFRA_SECTION "WuKongIM API: ${WUKONGIM_HTTP_URL}/health"
  add_line INFRA_SECTION "WuKongIM WS: ${WUKONGIM_WS_URL}"
fi

if service_is_running adminer; then
  add_line TOOLS_SECTION "Adminer: http://localhost:${ADMINER_PORT_VALUE} (system=PostgreSQL, server=postgres, user=${POSTGRES_USERNAME}, password=${POSTGRES_SECRET}, db=${POSTGRES_DB_NAME})"
fi

if service_is_running tgo-celery-flower; then
  add_line TOOLS_SECTION "Flower: http://localhost:${FLOWER_PORT_VALUE}"
fi

if service_is_running tgo-device-control-agentos; then
  add_line TOOLS_SECTION "AgentOS: http://localhost:${AGENTOS_PORT_VALUE} (health: http://localhost:${AGENTOS_PORT_VALUE}/health)"
fi

printf 'TGO dev environment is ready.\n\n'

if [ -z "$WEB_SECTION$API_SECTION$INFRA_SECTION$TOOLS_SECTION" ]; then
  printf 'No running services detected.\n'
  exit 0
fi

print_section "Web" "$WEB_SECTION"
print_section "APIs" "$API_SECTION"
print_section "Infra" "$INFRA_SECTION"
print_section "Tools" "$TOOLS_SECTION"
