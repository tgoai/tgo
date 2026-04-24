#!/bin/bash
# Wait for development dependencies and run all migrations in order.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${ENV_FILE:-.env.dev}"
DRY_RUN="false"

if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN="true"
fi

if [ ! -f "$PROJECT_ROOT/$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

set -a
source "$PROJECT_ROOT/$ENV_FILE"
set +a

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f docker-compose.dev.yml)
MIGRATIONS=(
  migrate-api
  migrate-ai
  migrate-rag
  migrate-platform
  migrate-workflow
  migrate-plugin
  migrate-device
)

wait_step() {
  local mode="$1"
  local target="$2"
  local value="${3:-}"

  if [ "$DRY_RUN" = "true" ]; then
    if [ "$mode" = "tcp" ]; then
      echo "wait tcp $target:$value"
    else
      echo "wait http $target"
    fi
    return 0
  fi

  if [ "$mode" = "tcp" ]; then
    "$PROJECT_ROOT/scripts/dev/wait-for.sh" tcp "$target" "$value"
  else
    "$PROJECT_ROOT/scripts/dev/wait-for.sh" http "$target"
  fi
}

run_migration() {
  local service="$1"

  if [ "$DRY_RUN" = "true" ]; then
    echo "run $service"
    return 0
  fi

  echo "Running migration: $service"
  (cd "$PROJECT_ROOT" && "${COMPOSE[@]}" run --rm --no-deps "$service")
}

wait_step tcp localhost "${POSTGRES_PORT:-5432}"
wait_step tcp localhost "${REDIS_PORT:-6379}"
wait_step http "http://localhost:5001/health"

for service in "${MIGRATIONS[@]}"; do
  run_migration "$service"
done
