#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

TOOLS_COMPOSE_FILE="docker-compose.tools.yml"

if [ ! -f "$TOOLS_COMPOSE_FILE" ]; then
  echo "[ERROR] $TOOLS_COMPOSE_FILE not found in current directory."
  exit 1
fi

CMD=${1:-}

case "$CMD" in
  start)
    echo "[INFO] Starting debug tools (kafka-ui, adminer)..."
    docker compose -f "$TOOLS_COMPOSE_FILE" up -d
    ;;
  stop)
    echo "[INFO] Stopping debug tools (kafka-ui, adminer)..."
    docker compose -f "$TOOLS_COMPOSE_FILE" down
    ;;
  *)
    echo "Usage: $0 {start|stop}"
    exit 1
    ;;
 esac

