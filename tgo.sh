#!/usr/bin/env bash
set -euo pipefail

# Move to repo root
cd "$(dirname "$0")"

MAIN_COMPOSE_IMAGE="docker-compose.yml"
MAIN_COMPOSE_SOURCE="docker-compose.source.yml"
MAIN_COMPOSE_CN="docker-compose.cn.yml"
TOOLS_COMPOSE="docker-compose.tools.yml"
ENV_FILE=".env"

# Global flag for China mirror support
USE_CN_MIRROR=false

usage() {
  cat <<'EOF'
Usage: ./tgo.sh <command> [options]

Commands:
  help                                Show this help message
  install [--source] [--cn]           Deploy all services (migrate, start; default: use pre-built images)
  uninstall [--source] [--cn]         Stop and remove all services (prompts for data deletion)
  service <start|stop|remove> [--source] [--cn]
                                      Start/stop/remove core services
  tools <start|stop>                  Start/stop debug tools (kafka-ui, adminer)
  build [--source] [--cn] <service>   Rebuild specific service from source (api|rag|ai|platform|web|widget|all)

Options:
  --source    Build and run services from local source code (repos/)
  --cn        Use China mirrors (Alibaba Cloud ACR for images, Gitee for git repos)

Notes:
  - By default, commands use image-based deployment (docker-compose.yml, images from GHCR).
  - Pass --source to build and run services from local source (docker-compose.yml + docker-compose.source.yml).
  - Pass --cn to use China-based mirrors for faster access in mainland China.
  - Options can be combined: ./tgo.sh install --source --cn
EOF
}

# Note: docker-compose.cn.yml is now a static file in the repository
# (no longer auto-generated)

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
  local compose_file_args=${1:-"-f $MAIN_COMPOSE_IMAGE"}
  echo "[INFO] Waiting for Postgres to be ready..."
  local retries=60
  local user="${POSTGRES_USER:-tgo}"
  local db="${POSTGRES_DB:-tgo}"
  for _ in $(seq 1 "$retries"); do
    if docker compose --env-file "$ENV_FILE" $compose_file_args exec -T postgres pg_isready -U "$user" -d "$db" >/dev/null 2>&1; then
      echo "[INFO] Postgres is ready."
      return 0
    fi
    sleep 2
  done
  echo "[ERROR] Postgres was not ready in time."
  return 1
}

cmd_install() {
  local mode="image"
  local use_cn=false

  # Parse arguments (support --source and --cn in any order)
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source)
        mode="source"
        shift
        ;;
      --cn)
        use_cn=true
        USE_CN_MIRROR=true
        shift
        ;;
      *)
        echo "[ERROR] Unknown argument to install: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  ensure_env_files
  ensure_api_secret_key

  local compose_file_args="-f $MAIN_COMPOSE_IMAGE"
  if [ "$mode" = "source" ]; then
    if [ ! -f "$MAIN_COMPOSE_SOURCE" ]; then
      echo "[ERROR] $MAIN_COMPOSE_SOURCE not found. Cannot run in --source mode." >&2
      exit 1
    fi
    compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_SOURCE"
    echo "[INFO] Deployment mode: SOURCE (building images from local repos)."
  else
    if [ "$use_cn" = true ]; then
      compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_CN"
      echo "[INFO] Deployment mode: IMAGE (using pre-built images from Alibaba Cloud ACR)."
    else
      echo "[INFO] Deployment mode: IMAGE (using pre-built images from GHCR)."
    fi
  fi

  if [ "$mode" = "source" ]; then
    echo "[INFO] Building application images from source..."
    docker compose --env-file "$ENV_FILE" $compose_file_args build
  else
    if [ "$use_cn" = true ]; then
      echo "[INFO] Skipping local image build; Docker will pull images from Alibaba Cloud ACR."
    else
      echo "[INFO] Skipping local image build; Docker will pull images from GHCR."
    fi
  fi

  echo "[INFO] Starting core infrastructure (postgres, redis, kafka, wukongim)..."
  docker compose --env-file "$ENV_FILE" $compose_file_args up -d postgres redis kafka wukongim

  wait_for_postgres "$compose_file_args"

  echo "[INFO] Running Alembic migrations for tgo-rag..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm tgo-rag alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-ai..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm tgo-ai alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-api..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm tgo-api alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-platform..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -e PYTHONPATH=. tgo-platform alembic upgrade head

  echo "[INFO] Starting all core services..."
  docker compose --env-file "$ENV_FILE" $compose_file_args up -d
  echo "[INFO] All services are starting. Use 'docker compose ps' to inspect status."
}

cmd_uninstall() {
  local mode="image"
  local use_cn=false

  # Parse arguments (support --source and --cn in any order)
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source)
        mode="source"
        shift
        ;;
      --cn)
        use_cn=true
        USE_CN_MIRROR=true
        shift
        ;;
      *)
        echo "[ERROR] Unknown argument to uninstall: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  ensure_env_files

  local compose_file_args="-f $MAIN_COMPOSE_IMAGE"
  if [ "$mode" = "source" ]; then
    if [ ! -f "$MAIN_COMPOSE_SOURCE" ]; then
      echo "[ERROR] $MAIN_COMPOSE_SOURCE not found. Cannot run uninstall in --source mode." >&2
      exit 1
    fi
    compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_SOURCE"
    echo "[INFO] Uninstalling services in SOURCE mode."
  else
    if [ "$use_cn" = true ]; then
      compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_CN"
      echo "[INFO] Uninstalling services in IMAGE mode (China mirrors)."
    else
      echo "[INFO] Uninstalling services in IMAGE mode."
    fi
  fi

  echo "Do you want to delete all data (./data/ directory)? [y/N]"
  read -r answer
  case "$answer" in
    y|Y|yes|YES)
      echo "[INFO] Stopping services and removing images and volumes..."
      docker compose --env-file "$ENV_FILE" $compose_file_args down --rmi local -v || true
      if [ -d "data" ]; then
        echo "[INFO] Removing ./data directory..."
        rm -rf data
      fi
      ;;
    *)
      echo "[INFO] Stopping services and removing images (preserving data)..."
      docker compose --env-file "$ENV_FILE" $compose_file_args down --rmi local || true
      ;;
  esac
}

cmd_service() {
  local sub=${1:-}
  shift || true

  local mode="image"
  local use_cn=false

  # Parse arguments (support --source and --cn in any order)
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source)
        mode="source"
        shift
        ;;
      --cn)
        use_cn=true
        USE_CN_MIRROR=true
        shift
        ;;
      *)
        echo "[ERROR] Unknown argument to service: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  local compose_file_args="-f $MAIN_COMPOSE_IMAGE"
  if [ "$mode" = "source" ]; then
    if [ ! -f "$MAIN_COMPOSE_SOURCE" ]; then
      echo "[ERROR] $MAIN_COMPOSE_SOURCE not found. Cannot run service in --source mode." >&2
      exit 1
    fi
    compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_SOURCE"
  elif [ "$use_cn" = true ]; then
    compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_CN"
  fi

  case "$sub" in
    start)
      ensure_env_files
      echo "[INFO] Starting all core services (mode: $mode)..."
      docker compose --env-file "$ENV_FILE" $compose_file_args up -d
      ;;
    stop)
      ensure_env_files
      echo "[INFO] Stopping all core services (mode: $mode)..."
      docker compose --env-file "$ENV_FILE" $compose_file_args down
      ;;
    remove)
      ensure_env_files
      echo "[INFO] Stopping services and removing images (mode: $mode)..."
      docker compose --env-file "$ENV_FILE" $compose_file_args down --rmi local
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

  local mode="image"
  local use_cn=false

  # Parse arguments (support --source and --cn in any order)
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source)
        mode="source"
        shift
        ;;
      --cn)
        use_cn=true
        USE_CN_MIRROR=true
        shift
        ;;
      -*)
        echo "[ERROR] Unknown option: $1" >&2
        usage
        exit 1
        ;;
      *)
        # This is the service name, stop parsing options
        break
        ;;
    esac
  done

  if [ "$mode" != "source" ]; then
    echo "[ERROR] build is only supported in --source mode (local builds)." >&2
    echo "Usage: ./tgo.sh build --source [--cn] <service>" >&2
    exit 1
  fi

  local target=${1-}
  if [ -z "$target" ]; then
    echo "[ERROR] Missing service name for build." >&2
    usage
    exit 1
  fi
  shift || true

  if [ "$#" -gt 0 ]; then
    echo "[ERROR] Too many arguments for build." >&2
    usage
    exit 1
  fi

  case "$target" in
    api) services=(tgo-api) ;;
    rag) services=(tgo-rag tgo-rag-worker tgo-rag-beat tgo-rag-flower) ;;
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

  if [ ! -f "$MAIN_COMPOSE_SOURCE" ]; then
    echo "[ERROR] $MAIN_COMPOSE_SOURCE not found. Cannot build from source." >&2
    exit 1
  fi

  local compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_SOURCE"

  if [ "${#services[@]}" -eq 0 ]; then
    echo "[INFO] Rebuilding all services from source..."
    docker compose --env-file "$ENV_FILE" $compose_file_args build
    docker compose --env-file "$ENV_FILE" $compose_file_args up -d
  else
    echo "[INFO] Rebuilding services from source: ${services[*]}..."
    docker compose --env-file "$ENV_FILE" $compose_file_args build "${services[@]}"
    docker compose --env-file "$ENV_FILE" $compose_file_args up -d "${services[@]}"
  fi
}

main() {
  local cmd=${1:-help}
  shift || true
  case "$cmd" in
    help|-h|--help) usage ;;
    install) cmd_install "$@" ;;
    uninstall) cmd_uninstall "$@" ;;
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

