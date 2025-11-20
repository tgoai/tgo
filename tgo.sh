#!/usr/bin/env bash
set -euo pipefail

# Move to repo root
cd "$(dirname "$0")"

MAIN_COMPOSE="docker-compose.yml"
TOOLS_COMPOSE="docker-compose.tools.yml"
ENV_FILE=".env"

usage() {
  cat <<'EOF'
Usage: ./tgo.sh <command> [options]

Commands:
  help                    Show this help message
  install                 Deploy all services (build, migrate, start)
  uninstall               Stop and remove all services (prompts for data deletion)
  service start           Start all core services
  service stop            Stop all core services
  service remove          Stop services and remove images
  tools start             Start debug tools (kafka-ui, adminer)
  tools stop              Stop debug tools
  build <service>         Rebuild specific service (api|rag|ai|platform|web|widget|all)
EOF
}

ensure_env_files() {
  if [ ! -f "$ENV_FILE" ]; then
    cp .env.example "$ENV_FILE"
    echo "[INFO] Created .env from .env.example. Edit it if needed."
  fi

  if [ ! -d "envs" ] && [ -d "envs.docker" ]; then
    cp -R "envs.docker" "envs"
    echo "[INFO] Created envs/ from envs.docker."
  fi
}

ensure_api_secret_key() {
  local file="envs/tgo-api.env"
  [ -f "$file" ] || { echo "[WARN] $file not found; skipping SECRET_KEY generation"; return 0; }
  local placeholder="ad6b1be1e4f9d2b03419e0876d0d2a19c647c7ef1dd1d2d9d3f98a09b7b1c0e7"
  local current
  current=$(grep -E '^SECRET_KEY=' "$file" | head -n1 | cut -d= -f2- || true)
  if [ -z "$current" ] || [ "$current" = "$placeholder" ] || [ "$current" = "changeme" ] || [ ${#current} -lt 32 ]; then
    local newkey
    if command -v openssl >/dev/null 2>&1; then
      newkey=$(openssl rand -hex 32)
    elif command -v python3 >/dev/null 2>&1; then
      newkey=$(python3 - <<'PY'
import secrets; print(secrets.token_hex(32))
PY
)
    elif command -v python >/dev/null 2>&1; then
      newkey=$(python - <<'PY'
import secrets; print(secrets.token_hex(32))
PY
)
    else
      newkey=$(dd if=/dev/urandom bs=32 count=1 2>/dev/null | xxd -p -c 64 2>/dev/null || date +%s | shasum -a 256 | awk '{print $1}' | cut -c1-64)
    fi
    local tmp="${file}.tmp"
    if grep -qE '^SECRET_KEY=' "$file"; then
      awk -v nk="$newkey" 'BEGIN{FS=OFS="="} /^SECRET_KEY=/{print "SECRET_KEY",nk; next} {print $0}' "$file" > "$tmp" && mv "$tmp" "$file"
    else
      printf "\nSECRET_KEY=%s\n" "$newkey" >> "$file"
    fi
    echo "[INFO] Generated new SECRET_KEY for tgo-api."
  else
    echo "[INFO] SECRET_KEY already set and valid."
  fi
}

wait_for_postgres() {
  echo "[INFO] Waiting for Postgres to be ready..."
  local retries=60
  local user="${POSTGRES_USER:-tgo}"
  local db="${POSTGRES_DB:-tgo}"
  for _ in $(seq 1 "$retries"); do
    if docker compose --env-file "$ENV_FILE" exec -T postgres pg_isready -U "$user" -d "$db" >/dev/null 2>&1; then
      echo "[INFO] Postgres is ready."
      return 0
    fi
    sleep 2
  done
  echo "[ERROR] Postgres was not ready in time."
  return 1
}

cmd_install() {
  ensure_env_files
  ensure_api_secret_key

  echo "[INFO] Building application images..."
  docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" build

  echo "[INFO] Starting core infrastructure (postgres, redis, kafka, wukongim)..."
  docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" up -d postgres redis kafka wukongim

  wait_for_postgres

  echo "[INFO] Running Alembic migrations for tgo-rag..."
  docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" run --rm tgo-rag poetry run alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-ai..."
  docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" run --rm tgo-ai poetry run alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-api..."
  docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" run --rm tgo-api poetry run alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-platform..."
  docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" run --rm -e PYTHONPATH=. tgo-platform poetry run alembic upgrade head

  echo "[INFO] Starting all core services..."
  docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" up -d
  echo "[INFO] All services are starting. Use 'docker compose ps' to inspect status."
}

cmd_uninstall() {
  ensure_env_files
  echo "Do you want to delete all data (./data/ directory)? [y/N]"
  read -r answer
  case "$answer" in
    y|Y|yes|YES)
      echo "[INFO] Stopping services and removing images and volumes..."
      docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" down --rmi local -v || true
      if [ -d "data" ]; then
        echo "[INFO] Removing ./data directory..."
        rm -rf data
      fi
      ;;
    *)
      echo "[INFO] Stopping services and removing images (preserving data)..."
      docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" down --rmi local || true
      ;;
  esac
}

cmd_service() {
  local sub=${1:-}
  case "$sub" in
    start)
      ensure_env_files
      echo "[INFO] Starting all core services..."
      docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" up -d
      ;;
    stop)
      ensure_env_files
      echo "[INFO] Stopping all core services..."
      docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" down
      ;;
    remove)
      ensure_env_files
      echo "[INFO] Stopping services and removing images..."
      docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" down --rmi local
      ;;
    *)
      echo "[ERROR] Unknown service subcommand: $sub" >&2
      usage
      exit 1
      ;;
  esac
}

cmd_tools() {
  local sub=${1:-}
  if [ ! -f "$TOOLS_COMPOSE" ]; then
    echo "[ERROR] $TOOLS_COMPOSE not found in repository root." >&2
    exit 1
  fi
  case "$sub" in
    start)
      echo "[INFO] Starting debug tools (kafka-ui, adminer)..."
      docker compose -f "$TOOLS_COMPOSE" up -d
      ;;
    stop)
      echo "[INFO] Stopping debug tools (kafka-ui, adminer)..."
      docker compose -f "$TOOLS_COMPOSE" down
      ;;
    *)
      echo "[ERROR] Unknown tools subcommand: $sub" >&2
      usage
      exit 1
      ;;
  esac
}

cmd_build() {
  ensure_env_files
  local target=${1:-}
  if [ -z "$target" ]; then
    echo "[ERROR] Missing service name for build." >&2
    usage
    exit 1
  fi

  case "$target" in
    api) services=(tgo-api) ;;
    rag) services=(tgo-rag) ;;
    ai) services=(tgo-ai) ;;
    platform) services=(tgo-platform) ;;
    web) services=(tgo-web) ;;
    widget) services=(tgo-widget-app) ;;
    all) services=() ;;
    *)
      echo "[ERROR] Unknown service: $target" >&2
      echo "Supported: api, rag, ai, platform, web, widget, all" >&2
      exit 1
      ;;
  esac

  if [ "${#services[@]}" -eq 0 ]; then
    echo "[INFO] Rebuilding all services..."
    docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" build
    docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" up -d
  else
    echo "[INFO] Rebuilding services: ${services[*]}..."
    docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" build "${services[@]}"
    docker compose --env-file "$ENV_FILE" -f "$MAIN_COMPOSE" up -d "${services[@]}"
  fi
}

main() {
  local cmd=${1:-help}
  shift || true
  case "$cmd" in
    help|-h|--help) usage ;;
    install) cmd_install ;;
    uninstall) cmd_uninstall ;;
    service) cmd_service "$@" ;;
    tools) cmd_tools "$@" ;;
    build) cmd_build "$@" ;;
    *)
      echo "[ERROR] Unknown command: $cmd" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"

