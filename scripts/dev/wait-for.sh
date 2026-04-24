#!/bin/bash
# Wait for a TCP socket or HTTP endpoint to become ready.

set -euo pipefail

MODE="${1:-}"
TARGET="${2:-}"
VALUE="${3:-}"
ATTEMPTS="${WAIT_FOR_ATTEMPTS:-60}"
SLEEP_SECONDS="${WAIT_FOR_SLEEP_SECONDS:-2}"

if [ -z "$MODE" ]; then
  echo "Usage: $0 tcp <host> <port> | http <url>"
  exit 1
fi

check_tcp() {
  local host="$1"
  local port="$2"
  python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.create_connection((host, port), timeout=2):
    pass
PY
}

check_http() {
  local url="$1"
  curl -fsS "$url" > /dev/null
}

for attempt in $(seq 1 "$ATTEMPTS"); do
  if [ "$MODE" = "tcp" ]; then
    if check_tcp "$TARGET" "$VALUE"; then
      echo "Ready: tcp $TARGET:$VALUE"
      exit 0
    fi
    label="tcp $TARGET:$VALUE"
  elif [ "$MODE" = "http" ]; then
    if check_http "$TARGET"; then
      echo "Ready: http $TARGET"
      exit 0
    fi
    label="http $TARGET"
  else
    echo "Unsupported mode: $MODE"
    exit 1
  fi

  echo "Waiting for $label ($attempt/$ATTEMPTS)..."
  sleep "$SLEEP_SECONDS"
done

echo "Timed out waiting for $label"
exit 1
