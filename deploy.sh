#!/usr/bin/env bash
set -euo pipefail

# Move to script dir
cd "$(dirname "$0")"

# Prepare .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit it if needed."
fi



# Ensure API SECRET_KEY is generated on first deploy
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
    echo "[OK] Generated new SECRET_KEY for tgo-api"
  else
    echo "[OK] SECRET_KEY already set and non-placeholder; keep existing"
  fi
}

# Ensure envs directory exists (copy from envs.docker on first run)
if [ ! -d "envs" ]; then
  if [ -d "envs.docker" ]; then
    cp -R "envs.docker" "envs"
    echo "[OK] Created envs/ from envs.docker"
  else
    echo "[WARN] envs/ not found and envs.docker/ missing; proceeding without copying"
  fi
fi


# Generate a secure SECRET_KEY for tgo-api if needed
ensure_api_secret_key

# Helper: wait for Postgres healthy
wait_for_postgres() {
  echo "[INFO] Waiting for Postgres to be ready..."
  local retries=60
  local user="${POSTGRES_USER:-tgo}"
  local db="${POSTGRES_DB:-tgo}"
  for i in $(seq 1 "$retries"); do
    if docker compose exec -T postgres pg_isready -U "$user" -d "$db" >/dev/null 2>&1; then
      echo "[OK] Postgres is ready"
      return 0
    fi
    sleep 2
  done
  echo "[ERROR] Postgres was not ready in time"
  return 1
}

# Allow ./deploy.sh stop/remove to manage lifecycle without redeploy
CMD=${1:-}
if [ "$CMD" = "stop" ]; then
  echo "[INFO] Stopping all core services (docker compose down)..."
  docker compose --env-file .env down
  exit 0
elif [ "$CMD" = "remove" ]; then
  echo "[INFO] Stopping all core services and removing related images (docker compose down --rmi local)..."
  docker compose --env-file .env down --rmi local
  exit 0
fi


# 1) Build application images first so migrations use the latest code
#    This ensures we don't run Alembic with a missing or outdated image.
docker compose --env-file .env build

# 2) Start core infra first (DB/Cache/Message)
docker compose --env-file .env up -d postgres redis kafka wukongim

# 3) Wait for DB ready (required by migrations)
wait_for_postgres

# 4) Run database migrations so users don't need to run them manually
echo "[INFO] Running Alembic migrations for tgo-rag..."
docker compose --env-file .env run --rm tgo-rag poetry run alembic upgrade head

echo "[INFO] Running Alembic migrations for tgo-ai..."
docker compose --env-file .env run --rm tgo-ai poetry run alembic upgrade head

echo "[INFO] Running Alembic migrations for tgo-api..."
docker compose --env-file .env run --rm tgo-api poetry run alembic upgrade head

echo "[INFO] Running Alembic migrations for tgo-platform..."
docker compose --env-file .env run --rm -e PYTHONPATH=. tgo-platform poetry run alembic upgrade head

# 5) Start all services (images already built above)
docker compose --env-file .env up -d

echo "\nAll services are starting. Use 'docker compose ps' and logs to check status."

