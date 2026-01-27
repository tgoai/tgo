#!/usr/bin/env bash
set -euo pipefail

# Move to repo root
cd "$(dirname "$0")"

MAIN_COMPOSE_IMAGE="docker-compose.yml"
MAIN_COMPOSE_SOURCE="docker-compose.source.yml"
MAIN_COMPOSE_CN="docker-compose.cn.yml"
TOOLS_COMPOSE="docker-compose.tools.yml"
ENV_FILE=".env"
CONFIG_FILE="./data/.tgo-install-mode"

# Global flag for China mirror support
USE_CN_MIRROR=false

# =============================================================================
# Common Helper Functions
# =============================================================================

# Get compose file arguments based on mode and cn flag
# Usage: get_compose_file_args <mode> <use_cn>
# Returns: compose file arguments string
get_compose_file_args() {
  local mode="${1:-image}"
  local use_cn="${2:-false}"
  
  local compose_args="-f $MAIN_COMPOSE_IMAGE"
  
  if [ "$mode" = "source" ]; then
    if [ ! -f "$MAIN_COMPOSE_SOURCE" ]; then
      echo "[ERROR] $MAIN_COMPOSE_SOURCE not found. Cannot run in --source mode." >&2
      return 1
    fi
    compose_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_SOURCE"
  elif [ "$use_cn" = "true" ]; then
    if [ -f "$MAIN_COMPOSE_CN" ]; then
      compose_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_CN"
    fi
  fi
  
  echo "$compose_args"
}

# Run all database migrations
# Usage: run_all_migrations <compose_file_args>
run_all_migrations() {
  local compose_file_args="$1"
  
  echo "[INFO] Running Alembic migrations for tgo-rag..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-rag alembic upgrade head
  
  echo "[INFO] Running Alembic migrations for tgo-ai..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-ai alembic upgrade head
  
  echo "[INFO] Running Alembic migrations for tgo-api..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-api alembic upgrade head
  
  echo "[INFO] Running Alembic migrations for tgo-platform..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T -e PYTHONPATH=. tgo-platform alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-workflow..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-workflow alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-plugin-runtime..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-plugin-runtime alembic upgrade head

  echo "[INFO] Running Alembic migrations for tgo-device-control..."
  docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-device-control alembic upgrade head
}

# Start core infrastructure services
# Usage: start_infrastructure <compose_file_args>
start_infrastructure() {
  local compose_file_args="$1"
  
  echo "[INFO] Starting core infrastructure (postgres, redis, wukongim)..."
  docker compose --env-file "$ENV_FILE" $compose_file_args up -d postgres redis wukongim
}

# Log deployment mode
# Usage: log_deploy_mode <mode> <use_cn> <action>
log_deploy_mode() {
  local mode="$1"
  local use_cn="$2"
  local action="${3:-Starting}"
  
  if [ "$mode" = "source" ]; then
    echo "[INFO] $action services in SOURCE mode."
  elif [ "$use_cn" = "true" ]; then
    echo "[INFO] $action services in IMAGE mode (China mirrors)."
  else
    echo "[INFO] $action services in IMAGE mode (GHCR)."
  fi
}

# =============================================================================
# WuKongIM Plugins
# =============================================================================

# IMPORTANT: WuKongIM runs in Docker, so we always install the Linux amd64 plugin asset.
WUKONGIM_SEARCH_PLUGIN_FILE="wk.plugin.search-linux-amd64.wkp"

get_wukongim_plugins_latest_tag() {
  # Try to detect the latest release tag from GitHub/Gitee.
  # Output: tag (e.g. v1.1.0) or empty.
  local use_cn="${1:-false}"

  if ! command -v curl >/dev/null 2>&1; then
    echo ""
    return 0
  fi

  if [ "$use_cn" = "true" ]; then
    # 1) Gitee API (best-effort, no jq)
    local api_url="https://gitee.com/api/v5/repos/WuKongDev/plugins/releases/latest"
    local tag
    tag=$(
      curl -fsSL --connect-timeout 8 --max-time 12 "$api_url" 2>/dev/null | \
        sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]\+\)".*/\1/p' | head -n 1
    )
    if [ -n "$tag" ]; then
      echo "$tag"
      return 0
    fi

    # 2) Gitee releases HTML fallback (grab first vX.Y.Z-like token)
    tag=$(
      curl -fsSL --connect-timeout 8 --max-time 12 "https://gitee.com/WuKongDev/plugins/releases" 2>/dev/null | \
        grep -Eo 'v[0-9]+\.[0-9]+\.[0-9]+' | head -n 1
    )
    if [ -n "$tag" ]; then
      echo "$tag"
      return 0
    fi

    echo ""
    return 0
  fi

  # GitHub:
  # 1) GitHub API first (best-effort)
  local api_url="https://api.github.com/repos/WuKongIM/plugins/releases/latest"
  local tag
  tag=$(
    curl -fsSL --connect-timeout 8 --max-time 12 "$api_url" 2>/dev/null | \
      sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]\+\)".*/\1/p' | head -n 1
  )
  if [ -n "$tag" ]; then
    echo "$tag"
    return 0
  fi

  # 2) Follow redirect of /releases/latest and parse .../tag/<tag>
  local effective
  effective=$(curl -sSIL --connect-timeout 8 --max-time 12 -o /dev/null -w "%{url_effective}" "https://github.com/WuKongIM/plugins/releases/latest" 2>/dev/null || true)
  tag=$(echo "$effective" | sed -n 's#.*/tag/\([^/]\+\).*#\1#p' | head -n 1)
  if [ -n "$tag" ]; then
    echo "$tag"
    return 0
  fi

  echo ""
}

install_wukongim_search_plugin() {
  # Install WuKongIM "search" plugin into ./data/wukongim/plugins before starting the container.
  local plugins_dir="./data/wukongim/plugins"
  local plugin_file="$WUKONGIM_SEARCH_PLUGIN_FILE"

  local use_cn="false"
  [ "${USE_CN_MIRROR:-false}" = "true" ] && use_cn="true"

  # Allow manual override via .env:
  #   WUKONGIM_PLUGIN_SEARCH_VERSION=v1.1.0
  #   WUKONGIM_PLUGIN_SEARCH_VERSION=latest
  local override_version=""
  override_version=$(grep -E "^WUKONGIM_PLUGIN_SEARCH_VERSION=" ".env" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)
  override_version=$(echo "$override_version" | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")

  local tag=""
  if [ -n "$override_version" ] && [ "$override_version" != "latest" ]; then
    tag="$override_version"
  else
    tag=$(get_wukongim_plugins_latest_tag "$use_cn")
  fi
  tag="${tag:-v1.1.0}"  # final fallback

  # Download source: GitHub for global; Gitee for CN mirror.
  local base_url
  if [ "$use_cn" = "true" ]; then
    base_url="https://gitee.com/WuKongDev/plugins/releases/download/${tag}"
  else
    base_url="https://github.com/WuKongIM/plugins/releases/download/${tag}"
  fi

  local url="${base_url}/${plugin_file}"
  local dest="${plugins_dir}/${plugin_file}"

  echo "[INFO] Ensuring WuKongIM search plugin is installed..."
  echo "[INFO] Plugin: $plugin_file (Docker/WuKongIM)"
  echo "[INFO] Version: $tag"
  echo "[INFO] Source: $url"

  mkdir -p "$plugins_dir"

  # Best-effort permissions: align with other data dirs strategy.
  chmod 755 "./data/wukongim" 2>/dev/null || true
  chmod 755 "$plugins_dir" 2>/dev/null || true

  # Download if missing
  if [ -f "$dest" ]; then
    echo "  ✓ Plugin already exists: $dest"
  else
    echo "  Downloading plugin to: $dest"
    local tmp="${dest}.tmp"
    if command -v curl >/dev/null 2>&1; then
      curl -fL --connect-timeout 10 --retry 3 --retry-delay 1 -o "$tmp" "$url" || {
        rm -f "$tmp" 2>/dev/null || true
        echo "[WARN] Failed to download WuKongIM search plugin. You can download it manually and place it under $plugins_dir"
        echo "[WARN] GitHub releases: https://github.com/WuKongIM/plugins/releases"
        echo "[WARN] Gitee releases (CN): https://gitee.com/WuKongDev/plugins/releases"
        return 0
      }
    elif command -v wget >/dev/null 2>&1; then
      wget -O "$tmp" "$url" || {
        rm -f "$tmp" 2>/dev/null || true
        echo "[WARN] Failed to download WuKongIM search plugin. You can download it manually and place it under $plugins_dir"
        echo "[WARN] GitHub releases: https://github.com/WuKongIM/plugins/releases"
        echo "[WARN] Gitee releases (CN): https://gitee.com/WuKongDev/plugins/releases"
        return 0
      }
    else
      echo "[WARN] Neither curl nor wget is available; cannot auto-download plugin."
      echo "[WARN] Please download $plugin_file and put it under $plugins_dir, then run: chmod +x $plugin_file"
      echo "[WARN] GitHub releases: https://github.com/WuKongIM/plugins/releases"
      echo "[WARN] Gitee releases (CN): https://gitee.com/WuKongDev/plugins/releases"
      return 0
    fi

    mv "$tmp" "$dest"
    echo "  ✓ Downloaded: $dest"
  fi

  chmod +x "$dest" 2>/dev/null || true
  echo "  ✓ chmod +x: $dest"
}

# =============================================================================
# Port Detection and Auto-Allocation Functions
# =============================================================================

# Check if a port is in use (cross-platform: macOS and Linux)
# Returns 0 if port is in use, 1 if port is available
is_port_in_use() {
  local port="$1"

  # Try lsof first (works on both macOS and Linux)
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i :"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0  # Port is in use
    fi
  # Fall back to netstat
  elif command -v netstat >/dev/null 2>&1; then
    local os_type
    os_type=$(uname -s)
    case "$os_type" in
      Darwin)
        # macOS netstat
        if netstat -an -p tcp 2>/dev/null | grep -E "\.${port}\s+.*LISTEN" >/dev/null; then
          return 0
        fi
        ;;
      Linux)
        # Linux netstat
        if netstat -tuln 2>/dev/null | grep -E ":${port}\s+" >/dev/null; then
          return 0
        fi
        ;;
    esac
  # Try ss on Linux
  elif command -v ss >/dev/null 2>&1; then
    if ss -tuln 2>/dev/null | grep -E ":${port}\s+" >/dev/null; then
      return 0
    fi
  fi

  return 1  # Port is available
}

# Check if a port is used by the TGO nginx container
# Returns 0 if used by tgo-nginx, 1 otherwise
is_port_used_by_tgo_nginx() {
  local port="$1"

  # Check if tgo-nginx container is running
  if ! docker ps --filter "name=tgo-nginx" --filter "status=running" --format "{{.Names}}" 2>/dev/null | grep -q "tgo-nginx"; then
    return 1  # Container not running
  fi

  # Check if tgo-nginx is using this port
  # Method 1: Check docker port mappings
  if docker port tgo-nginx 2>/dev/null | grep -E "^(80|443)/tcp -> .*:${port}$" >/dev/null; then
    return 0  # tgo-nginx is using this port
  fi

  # Method 2: Check container's published ports in docker inspect
  if docker inspect tgo-nginx --format='{{range $p, $conf := .NetworkSettings.Ports}}{{range $conf}}{{.HostPort}}{{"\n"}}{{end}}{{end}}' 2>/dev/null | grep -q "^${port}$"; then
    return 0  # tgo-nginx is using this port
  fi

  return 1  # Port not used by tgo-nginx
}

# Find an available port starting from a given port
# Usage: find_available_port <start_port> [max_attempts]
find_available_port() {
  local start_port="$1"
  local max_attempts="${2:-100}"
  local port="$start_port"
  local attempts=0

  while [ $attempts -lt $max_attempts ]; do
    if ! is_port_in_use "$port"; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
    attempts=$((attempts + 1))
  done

  # No available port found
  echo ""
  return 1
}

# Check ports and configure them in .env
# This function checks HTTP (80) and HTTPS (443) ports
check_and_configure_ports() {
  echo ""
  echo "========================================="
  echo "  Port Configuration"
  echo "========================================="
  echo ""

  local http_port=80
  local https_port=443
  local http_port_changed=false
  local https_port_changed=false

  # Read current port configuration from .env if exists
  # Note: docker-compose.yml uses NGINX_PORT and NGINX_SSL_PORT
  local current_http_port=""
  local current_https_port=""
  if [ -f "$ENV_FILE" ]; then
    current_http_port=$(grep -E "^NGINX_PORT=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "")
    current_https_port=$(grep -E "^NGINX_SSL_PORT=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "")
  fi

  # Use current configured ports if set, otherwise use defaults
  http_port="${current_http_port:-80}"
  https_port="${current_https_port:-443}"

  echo "[INFO] Checking port availability..."

  # Check HTTP port
  if is_port_in_use "$http_port"; then
    if is_port_used_by_tgo_nginx "$http_port"; then
      echo "  ✓ Port $http_port is used by TGO Nginx (OK for re-install)"
    else
      echo "  ⚠ Port $http_port is occupied by another process"

      # Find an available port starting from 8080
      local new_http_port
      new_http_port=$(find_available_port 8080)

      if [ -n "$new_http_port" ]; then
        echo "  → Auto-assigned new HTTP port: $new_http_port"
        http_port="$new_http_port"
        http_port_changed=true
      else
        echo "  ❌ Could not find an available HTTP port"
        echo "[ERROR] Please free up port 80 or manually configure NGINX_PORT in .env"
        return 1
      fi
    fi
  else
    echo "  ✓ Port $http_port is available"
  fi

  # Check HTTPS port
  if is_port_in_use "$https_port"; then
    if is_port_used_by_tgo_nginx "$https_port"; then
      echo "  ✓ Port $https_port is used by TGO Nginx (OK for re-install)"
    else
      echo "  ⚠ Port $https_port is occupied by another process"

      # Find an available port starting from 8443
      local new_https_port
      new_https_port=$(find_available_port 8443)

      if [ -n "$new_https_port" ]; then
        echo "  → Auto-assigned new HTTPS port: $new_https_port"
        https_port="$new_https_port"
        https_port_changed=true
      else
        echo "  ❌ Could not find an available HTTPS port"
        echo "[ERROR] Please free up port 443 or manually configure NGINX_SSL_PORT in .env"
        return 1
      fi
    fi
  else
    echo "  ✓ Port $https_port is available"
  fi

  # Update .env file with port configuration (using NGINX_PORT/NGINX_SSL_PORT to match docker-compose.yml)
  update_env_var "NGINX_PORT" "$http_port"
  update_env_var "NGINX_SSL_PORT" "$https_port"

  echo ""

  # Show summary if ports were changed
  if [ "$http_port_changed" = true ] || [ "$https_port_changed" = true ]; then
    echo "========================================="
    echo "  ⚠️  Port Configuration Changed"
    echo "========================================="
    echo ""
    echo "The default ports were occupied by other processes."
    echo "TGO has been configured to use the following ports:"
    echo ""
    if [ "$http_port_changed" = true ]; then
      echo "  • HTTP:  $http_port (instead of 80)"
    else
      echo "  • HTTP:  $http_port"
    fi
    if [ "$https_port_changed" = true ]; then
      echo "  • HTTPS: $https_port (instead of 443)"
    else
      echo "  • HTTPS: $https_port"
    fi
    echo ""
    echo "Access TGO using:"
    if [ "$http_port" != "80" ]; then
      echo "  • http://<your-server>:$http_port"
    else
      echo "  • http://<your-server>"
    fi
    echo ""
  else
    echo "[INFO] Port configuration: HTTP=$http_port, HTTPS=$https_port"
  fi

  return 0
}

usage() {
  cat <<'EOF'
Usage: ./tgo.sh <command> [options]

Commands:
  help                                Show this help message
  install [--source] [--cn]           Deploy all services (migrate, start; default: use pre-built images)
  up [--source] [--cn] [--remove-orphans]
                                      Start all services (without re-initialization)
  down [--volumes]                    Stop and remove all service containers
  upgrade [--source] [--cn] [--remove-orphans]
                                      Upgrade to latest version (remembers install mode if no options provided)
  uninstall [--source] [--cn]         Stop and remove all services (prompts for data deletion)
  doctor                              Check health status of all services
  service <start|stop|remove> [--source] [--cn]
                                      Start/stop/remove core services
  tools <start|stop>                  Start/stop debug tools (adminer, redis-insight)
  build <service>                     Rebuild specific service from source (api|rag|ai|plugin-runtime|device-control|workflow|platform|web|widget|all)
  config <subcommand> [args]          Configure domains and SSL certificates

Config Subcommands:
  web_domain <domain>                 Set web service domain (e.g., www.example.com)
  widget_domain <domain>              Set widget service domain (e.g., widget.example.com)
  api_domain <domain>                 Set API service domain (e.g., api.example.com)
  ws_domain <domain>                  Set WebSocket service domain (e.g., ws.example.com)
  http_port <port>                    Set Nginx HTTP port (default: 80)
  https_port <port>                   Set Nginx HTTPS port (default: 443)
  ssl_mode <auto|manual|none>         Set SSL mode (auto=Let's Encrypt, manual=custom, none=no SSL)
  ssl_email <email>                   Set Let's Encrypt email for certificate renewal
  ssl_manual <cert> <key> [domain]    Install manual SSL certificate
  setup_letsencrypt                   Setup Let's Encrypt certificates for all domains
  apply                               Regenerate Nginx configuration
  show                                Show current domain configuration

Options:
  --source          Build and run services from local source code (repos/)
  --cn              Use China mirrors (Alibaba Cloud ACR for images, Gitee for git repos)
  --remove-orphans  Remove containers for services not defined in the compose file

Notes:
  - By default, commands use image-based deployment (docker-compose.yml, images from GHCR).
  - Pass --source to build and run services from local source (docker-compose.yml + docker-compose.source.yml).
  - Pass --cn to use China-based mirrors for faster access in mainland China.
  - Options can be combined: ./tgo.sh install --source --cn
  - The 'install' command performs full initialization and then starts services.
  - The 'up' command starts services without re-initialization (useful after 'down').
  - The 'down' command stops all services; use --volumes to also remove data volumes.

Domain Configuration Examples:
  ./tgo.sh config web_domain www.example.com
  ./tgo.sh config widget_domain widget.example.com
  ./tgo.sh config api_domain api.example.com
  ./tgo.sh config ws_domain ws.example.com
  ./tgo.sh config ssl_mode auto
  ./tgo.sh config ssl_email admin@example.com
  ./tgo.sh config setup_letsencrypt
  ./tgo.sh config show

Upgrade Command:
  - The upgrade command remembers the mode used during install (saved in ./data/.tgo-install-mode)
  - If you provide --source or --cn flags, they will override the saved configuration
  - Examples:
    • ./tgo.sh install --cn          → ./tgo.sh upgrade (auto-uses --cn)
    • ./tgo.sh install --source      → ./tgo.sh upgrade (auto-uses --source)
    • ./tgo.sh upgrade --cn          → Override to use --cn for this upgrade
EOF
}

# Save install mode configuration
save_install_mode() {
  local mode="$1"
  local use_cn="$2"

  # Ensure data directory exists
  mkdir -p "$(dirname "$CONFIG_FILE")"

  # Write configuration
  cat > "$CONFIG_FILE" << EOF
# TGO Install Mode Configuration
# Auto-generated by ./tgo.sh install
# This file is used by ./tgo.sh upgrade to remember your deployment preferences

USE_SOURCE=$( [ "$mode" = "source" ] && echo "true" || echo "false" )
USE_CN=$( [ "$use_cn" = "true" ] && echo "true" || echo "false" )
EOF

  echo "[INFO] Saved install mode to $CONFIG_FILE"
}

# Load install mode configuration
load_install_mode() {
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "[WARN] No saved install mode found at $CONFIG_FILE"
    echo "[WARN] Using default mode: image-based deployment from GHCR"
    echo "false false"  # mode=image, use_cn=false
    return
  fi

  # Source the config file
  local use_source="false"
  local use_cn="false"

  # shellcheck disable=SC1090
  source "$CONFIG_FILE"

  # Convert to mode string
  local mode="image"
  if [ "${USE_SOURCE:-false}" = "true" ]; then
    mode="source"
  fi

  local cn_flag="false"
  if [ "${USE_CN:-false}" = "true" ]; then
    cn_flag="true"
  fi

  echo "$mode $cn_flag"
}

# Note: docker-compose.cn.yml is now a static file in the repository
# (no longer auto-generated)

# Helper function to sync environment variables from source to destination file
# without overwriting existing ones.
sync_env_file() {
  local src="$1"
  local dest="$2"
  
  if [ ! -f "$dest" ]; then
    cp "$src" "$dest"
    echo "[INFO] Added new env file: $dest"
    return
  fi

  local added_count=0
  local first_addition=true

  # Read source line by line
  while IFS= read -r line || [ -n "$line" ]; do
    # Only process lines that look like KEY=VALUE (start with alphanumeric/underscore followed by =)
    if [[ "$line" =~ ^[A-Za-z0-9_]+= ]]; then
      local key="${line%%=*}"
      # Check if key exists in destination file
      if ! grep -qE "^${key}=" "$dest"; then
        if [ "$first_addition" = true ]; then
          echo "[INFO] Syncing env vars for $dest"
          printf "\n# --- Added by upgrade on $(date +%Y-%m-%d) ---\n" >> "$dest"
          first_addition=false
        fi
        echo "$line" >> "$dest"
        echo "[INFO]   Added new config: $key"
        added_count=$((added_count + 1))
      fi
    fi
  done < "$src"
}

ensure_env_files() {
  if [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env.example" ]; then
      cp .env.example "$ENV_FILE"
      echo "[INFO] Created .env from .env.example. Edit it if needed."
    else
      # Create empty .env file with comments
      cat > "$ENV_FILE" << 'ENVEOF'
# TGO Environment Configuration
# Auto-generated by ./tgo.sh install

# Server host (IP address or domain name)
# Will be configured during installation
# SERVER_HOST=

# API Base URL (used by frontend apps)
# VITE_API_BASE_URL=

# PostgreSQL Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=tgo
POSTGRES_USER=tgo
POSTGRES_PASSWORD=tgo

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# Security Configuration
# SECRET_KEY is used for JWT authentication and plugin communication
SECRET_KEY=

# Nginx Ports
# NGINX_PORT=80
# NGINX_SSL_PORT=443
ENVEOF
      echo "[INFO] Created empty .env file."
    fi
  fi

  # Note: envs/ directory is no longer needed - all configuration is in root .env
  # Service-specific environment variables are now defined directly in docker-compose.yml
  
  # Source .env file to make variables available to the script
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$ENV_FILE"
    set +a
  fi
}

ensure_api_secret_key() {
  local env_file=".env"
  [ -f "$env_file" ] || { echo "[WARN] $env_file not found; skipping SECRET_KEY generation"; return 0; }
  
  local placeholder="ad6b1be1e4f9d2b03419e0876d0d2a19c647c7ef1dd1d2d9d3f98a09b7b1c0e7"
  local current
  current=$(grep -E '^SECRET_KEY=' "$env_file" | head -n1 | cut -d= -f2- || true)
  
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
    
    update_env_var "SECRET_KEY" "$newkey"
    echo "[INFO] Generated new SECRET_KEY in root .env file."
  else
    echo "[INFO] SECRET_KEY already set and valid in root .env file."
  fi
}

# Get server's public IP address
get_public_ip() {
  local ip=""
  
  # Try multiple services to get public IP
  if command -v curl >/dev/null 2>&1; then
    ip=$(curl -s --connect-timeout 5 https://api.ipify.org 2>/dev/null) || \
    ip=$(curl -s --connect-timeout 5 https://ifconfig.me 2>/dev/null) || \
    ip=$(curl -s --connect-timeout 5 https://icanhazip.com 2>/dev/null) || \
    ip=$(curl -s --connect-timeout 5 https://ipinfo.io/ip 2>/dev/null) || \
    ip=""
  elif command -v wget >/dev/null 2>&1; then
    ip=$(wget -qO- --timeout=5 https://api.ipify.org 2>/dev/null) || \
    ip=$(wget -qO- --timeout=5 https://ifconfig.me 2>/dev/null) || \
    ip=$(wget -qO- --timeout=5 https://icanhazip.com 2>/dev/null) || \
    ip=""
  fi
  
  # Clean up the IP (remove whitespace/newlines)
  ip=$(echo "$ip" | tr -d '[:space:]')
  
  # Validate IP format (basic check)
  if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "$ip"
  else
    echo ""
  fi
}

# Detect if running on macOS or Windows (via WSL/Git Bash/Cygwin)
is_desktop_os() {
  local os_type
  os_type=$(uname -s)
  
  case "$os_type" in
    Darwin)
      # macOS
      return 0
      ;;
    MINGW*|MSYS*|CYGWIN*)
      # Windows (Git Bash, MSYS2, Cygwin)
      return 0
      ;;
    Linux)
      # Check if running in WSL (Windows Subsystem for Linux)
      if grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
        return 0
      fi
      return 1
      ;;
    *)
      return 1
      ;;
  esac
}

# Check if domain configuration exists with non-localhost domains
has_domain_config() {
  local domain_config_file="./data/.tgo-domain-config"
  if [ ! -f "$domain_config_file" ]; then
    return 1
  fi

  # Check if any domain is configured (not empty and not localhost)
  local web_domain widget_domain api_domain
  web_domain=$(grep -E "^WEB_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
  widget_domain=$(grep -E "^WIDGET_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
  api_domain=$(grep -E "^API_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")

  # Return success if any domain is configured
  if [ -n "$web_domain" ] && [ "$web_domain" != "localhost" ]; then
    return 0
  fi
  if [ -n "$widget_domain" ] && [ "$widget_domain" != "localhost" ]; then
    return 0
  fi
  if [ -n "$api_domain" ] && [ "$api_domain" != "localhost" ]; then
    return 0
  fi

  return 1
}

# Validate and sanitize server host input
# Returns sanitized host or empty string if invalid
validate_server_host() {
  local input="$1"
  local sanitized="$input"
  
  # Remove leading/trailing whitespace
  sanitized=$(echo "$sanitized" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  
  # Check if input contains protocol prefix and remove it
  if [[ "$sanitized" =~ ^https?:// ]]; then
    echo "[WARN] Protocol prefix detected and will be removed" >&2
    sanitized=$(echo "$sanitized" | sed -E 's|^https?://||')
  fi
  
  # Remove trailing slash
  sanitized=$(echo "$sanitized" | sed 's|/$||')
  
  # Remove port number if present (e.g., :8080)
  if [[ "$sanitized" =~ :[0-9]+$ ]]; then
    echo "[WARN] Port number detected and will be removed" >&2
    sanitized=$(echo "$sanitized" | sed -E 's|:[0-9]+$||')
  fi
  
  # Remove path if present (e.g., /api)
  if [[ "$sanitized" =~ / ]]; then
    echo "[WARN] Path detected and will be removed" >&2
    sanitized=$(echo "$sanitized" | cut -d'/' -f1)
  fi
  
  # Validate the result is a valid IP or domain
  # IPv4 pattern
  local ipv4_pattern='^([0-9]{1,3}\.){3}[0-9]{1,3}$'
  # Domain pattern (simple validation)
  local domain_pattern='^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$'
  
  if [[ "$sanitized" =~ $ipv4_pattern ]]; then
    # Additional validation for IPv4 (each octet 0-255)
    local valid=true
    IFS='.' read -ra octets <<< "$sanitized"
    for octet in "${octets[@]}"; do
      if [ "$octet" -gt 255 ] 2>/dev/null; then
        valid=false
        break
      fi
    done
    if [ "$valid" = true ]; then
      echo "$sanitized"
      return 0
    fi
  elif [[ "$sanitized" =~ $domain_pattern ]] || [ "$sanitized" = "localhost" ]; then
    echo "$sanitized"
    return 0
  fi
  
  # Invalid input
  echo ""
  return 1
}

# Configure server host (IP or domain) and save to .env
configure_server_host() {
  echo ""
  echo "========================================="
  echo "  Server Host Configuration"
  echo "========================================="
  echo ""

  # Check if user has already configured domains via ./tgo.sh config
  if has_domain_config; then
    echo "[INFO] Existing domain configuration detected."
    echo "[INFO] Preserving your configured domains and environment variables."

    # Show current configuration
    local domain_config_file="./data/.tgo-domain-config"
    local web_domain widget_domain api_domain ssl_mode
    web_domain=$(grep -E "^WEB_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
    widget_domain=$(grep -E "^WIDGET_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
    api_domain=$(grep -E "^API_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
    ssl_mode=$(grep -E "^SSL_MODE=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "none")

    echo ""
    echo "  Current domains:"
    [ -n "$web_domain" ] && echo "    - Web:    $web_domain"
    [ -n "$widget_domain" ] && echo "    - Widget: $widget_domain"
    [ -n "$api_domain" ] && echo "    - API:    $api_domain"
    echo "    - SSL:    $ssl_mode"
    echo ""

    # Update env vars based on existing domain config
    update_domain_env_vars

    echo "[INFO] Environment variables synchronized with domain configuration."
    echo ""
    return 0
  fi

  # Check if SERVER_HOST is already configured in .env (for re-install scenarios)
  local existing_server_host=""
  if [ -f "$ENV_FILE" ]; then
    existing_server_host=$(grep -E "^SERVER_HOST=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "")
  fi

  if [ -n "$existing_server_host" ] && [ "$existing_server_host" != "localhost" ]; then
    echo "[INFO] Existing server host configuration detected: $existing_server_host"
    echo ""
    
    # Ask user if they want to keep the existing configuration
    local keep_config=""
    if [ -t 0 ]; then
      read -r -p "Keep existing configuration? [Y/n]: " keep_config
    else
      printf "Keep existing configuration? [Y/n]: "
      read -r keep_config < /dev/tty
    fi
    
    case "$keep_config" in
      n|N|no|NO)
        echo "[INFO] Will reconfigure server host..."
        ;;
      *)
        echo "[INFO] Keeping existing server host: $existing_server_host"
        
        # Re-sync URLs with current port configuration
        update_frontend_urls "$existing_server_host"
        
        echo "[INFO] URLs synchronized with port configuration"
        echo ""
        return 0
        ;;
    esac
  fi

  local default_host="localhost"
  local detected_ip=""

  # Check if running on desktop OS (macOS/Windows)
  if is_desktop_os; then
    echo "[INFO] Detected desktop OS (macOS/Windows), using localhost"
  else
    # Only try to get public IP on Linux servers
    echo "[INFO] Detecting server public IP..."
    detected_ip=$(get_public_ip)

    if [ -n "$detected_ip" ]; then
      default_host="$detected_ip"
      echo "[INFO] Detected public IP: $detected_ip"
    else
      echo "[WARN] Could not detect public IP, using localhost as default"
    fi
  fi

  echo ""
  echo "Enter server host (IP address or domain name):"
  echo ""
  echo "  Examples:"
  echo "    - $default_host (detected)"
  echo "    - 192.168.1.100 (private IP)"
  echo "    - www.example.com (domain)"
  echo ""
  echo "  Note: Do NOT include http://, https://, port, or path"
  echo ""

  local server_host=""
  local max_attempts=3
  local attempt=0

  while [ $attempt -lt $max_attempts ]; do
    # Read from /dev/tty to ensure we get input from terminal even when piped
    local user_input=""
    if [ -t 0 ]; then
      read -r -p "Server host [$default_host]: " user_input
    else
      printf "Server host [$default_host]: "
      read -r user_input < /dev/tty
    fi

    local input_to_validate="${user_input:-$default_host}"
    server_host=$(validate_server_host "$input_to_validate")

    if [ -n "$server_host" ]; then
      [ "$server_host" != "$input_to_validate" ] && echo "[INFO] Sanitized input: $input_to_validate → $server_host"
      break
    fi

    attempt=$((attempt + 1))
    if [ $attempt -lt $max_attempts ]; then
      echo "[ERROR] Invalid server host: $input_to_validate"
      echo "[ERROR] Please enter a valid IP address or domain name (without http://, port, or path)"
      echo ""
    else
      echo "[ERROR] Too many invalid attempts, using default: $default_host"
      server_host="$default_host"
    fi
  done
  
  # Determine protocol (http for IP, could be https for domain)
  local protocol="http"
  
  # Read configured port from .env (may have been changed by check_and_configure_ports)
  local nginx_port=""
  if [ -f "$ENV_FILE" ]; then
    nginx_port=$(grep -E "^NGINX_PORT=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "")
  fi
  nginx_port="${nginx_port:-80}"
  
  # Build port suffix for URLs (only if non-standard port)
  local port_suffix=""
  if [ "$nginx_port" != "80" ]; then
    port_suffix=":${nginx_port}"
  fi
  
  # Build the base URL with port if needed
  local api_base_url="${protocol}://${server_host}${port_suffix}/api"
  local widget_base_url="${protocol}://${server_host}${port_suffix}/widget"
  
  echo ""
  echo "[INFO] Configured server host: $server_host"
  if [ -n "$port_suffix" ]; then
    echo "[INFO] Using non-standard port: $nginx_port"
  fi
  echo "[INFO] API URL: $api_base_url"
  echo "[INFO] Widget URL: $widget_base_url"
  
  # Update .env file
  update_env_var "SERVER_HOST" "$server_host"
  update_frontend_urls "$server_host"
  
  echo ""
  echo "[INFO] Configuration saved to .env"
  echo ""
}

# Update frontend URLs in .env based on host and port
# Usage: update_frontend_urls <host>
update_frontend_urls() {
  local host="$1"
  local protocol="http"
  
  # Read configured port from .env
  local nginx_port=""
  if [ -f "$ENV_FILE" ]; then
    nginx_port=$(grep -E "^NGINX_PORT=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "")
  fi
  nginx_port="${nginx_port:-80}"
  
  # Build port suffix for URLs (only if non-standard port)
  local port_suffix=""
  if [ "$nginx_port" != "80" ]; then
    port_suffix=":${nginx_port}"
  fi
  
  local api_base_url="${protocol}://${host}${port_suffix}/api"
  local widget_preview_url="${protocol}://${host}${port_suffix}/widget/"
  local widget_script_base="${protocol}://${host}${port_suffix}/widget/tgo-widget-sdk.js"
  local widget_demo_url="${protocol}://${host}${port_suffix}/widget/demo.html"

  update_env_var "VITE_API_BASE_URL" "$api_base_url"
  update_env_var "VITE_WIDGET_PREVIEW_URL" "$widget_preview_url"
  update_env_var "VITE_WIDGET_SCRIPT_BASE" "$widget_script_base"
  update_env_var "VITE_WIDGET_DEMO_URL" "$widget_demo_url"
  
  echo "[INFO] Updated API URL: $api_base_url"
  echo "[INFO] Updated Widget URL: ${protocol}://${host}${port_suffix}/widget"
}

# Configure core services (DB, Redis) and save to .env
configure_core_settings() {
  echo ""
  echo "========================================="
  echo "  Core Services Configuration"
  echo "========================================="
  echo ""
  echo "[INFO] Using default settings for PostgreSQL and Redis."
  echo "[INFO] You can change these in the .env file later if needed."
  echo ""
  echo "  PostgreSQL: ${POSTGRES_USER:-tgo}@${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-tgo}"
  echo "  Redis:      ${REDIS_HOST:-redis}:${REDIS_PORT:-6379}"
  echo ""
}

# Update or add environment variable in .env file
update_env_var() {
  local key="$1"
  local value="$2"
  local env_file="$ENV_FILE"
  
  if grep -qE "^${key}=" "$env_file" 2>/dev/null; then
    # Update existing variable
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$env_file"
    rm -f "${env_file}.bak"
  else
    # Add new variable
    echo "${key}=${value}" >> "$env_file"
  fi
}

# Show installation complete message with access URLs
show_install_complete_message() {
  # Read SERVER_HOST and ports from .env file
  local server_host
  server_host=$(grep -E "^SERVER_HOST=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "localhost")
  server_host="${server_host:-localhost}"

  local nginx_port
  nginx_port=$(grep -E "^NGINX_PORT=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "80")
  nginx_port="${nginx_port:-80}"

  local protocol="http"
  local port_suffix=""
  if [ "$nginx_port" != "80" ]; then
    port_suffix=":${nginx_port}"
  fi

  local web_url="${protocol}://${server_host}${port_suffix}"
  local api_url="${protocol}://${server_host}${port_suffix}/api"

  echo ""
  echo "========================================="
  echo "  ✅ INSTALLATION COMPLETE"
  echo "========================================="
  echo ""
  echo "TGO has been successfully installed!"
  echo ""
  echo "Access URLs:"
  echo "  • Web Console:    $web_url"
  echo "  • API Endpoint:   $api_url"
  if [ "$nginx_port" != "80" ]; then
    echo ""
    echo "Note: Using non-standard port $nginx_port (default port 80 was occupied)"
  fi
  echo ""
  echo "Useful commands:"
  echo "  • Check status:   docker compose ps"
  echo "  • View logs:      docker compose logs -f"
  echo "  • Stop services:  ./tgo.sh down"
  echo "  • Restart:        ./tgo.sh up"
  echo "  • Upgrade:        ./tgo.sh upgrade"
  echo ""
  echo "Documentation: https://tgo.ai"
  echo ""

  # Real client IP notice (for visitor registration / analytics)
  # In some Docker setups, the source IP can be replaced by Docker gateway when userland-proxy is enabled.
  # This makes backend endpoints (e.g. /v1/visitors/register) only see 172.x/10.x/192.168.x instead of real client IP.
  local userland_proxy=""
  userland_proxy=$(docker info 2>/dev/null | grep -iE "^\s*Userland Proxy:\s*" | head -n 1 | awk -F: '{print $2}' | xargs || true)
  if [ -n "$userland_proxy" ]; then
    if [ "$userland_proxy" = "true" ]; then
      echo "========================================="
      echo "  ⚠ Real Client IP Notice"
      echo "========================================="
      echo ""
      echo "[WARN] Docker 'userland-proxy' is ENABLED on this host."
      echo "       In this mode, backend may NOT be able to obtain the real browser IP"
      echo "       (it may see Docker gateway IP like 172.18.0.1 instead)."
      echo ""
      echo "Fix (recommended): disable userland-proxy in Docker daemon config and restart Docker."
      echo "See: docs/GET_REAL_IP.md"
      echo ""
    fi
  fi
}

wait_for_postgres() {
  local compose_file_args=${1:-"-f $MAIN_COMPOSE_IMAGE"}
  echo "[INFO] Waiting for Postgres to be ready..."
  local retries=30
  local user="${POSTGRES_USER:-tgo}"
  local db="${POSTGRES_DB:-tgo}"
  local attempt=0
  for _ in $(seq 1 "$retries"); do
    attempt=$((attempt + 1))
    if docker compose --env-file "$ENV_FILE" $compose_file_args exec -T postgres pg_isready -U "$user" -d "$db" >/dev/null 2>&1; then
      echo "[INFO] Postgres is ready."
      return 0
    fi
    # Show progress every 5 attempts
    if [ $((attempt % 5)) -eq 0 ]; then
      echo "[INFO] Still waiting for Postgres... (attempt $attempt/$retries)"
    fi
    sleep 2
  done
  echo "[ERROR] Postgres was not ready in time after $retries attempts."
  echo "[ERROR] Try running manually: docker compose exec postgres pg_isready -U $user -d $db"
  return 1
}

cmd_up() {
  local mode="image"
  local use_cn=false
  local has_args=false
  local remove_orphans=false

  # Parse arguments (support --source, --cn, and --remove-orphans in any order)
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source) mode="source"; has_args=true; shift ;;
      --cn) use_cn=true; USE_CN_MIRROR=true; has_args=true; shift ;;
      --remove-orphans) remove_orphans=true; shift ;;
      *) echo "[ERROR] Unknown argument to up: $1" >&2; usage; exit 1 ;;
    esac
  done

  # If no arguments provided, load saved install mode configuration
  if [ "$has_args" = false ]; then
    echo "[INFO] Loading saved install mode configuration..."
    read -r mode use_cn <<< "$(load_install_mode)"
    [ "$use_cn" = "true" ] && USE_CN_MIRROR=true
  fi

  ensure_env_files

  local compose_file_args
  compose_file_args=$(get_compose_file_args "$mode" "$use_cn") || exit 1
  log_deploy_mode "$mode" "$use_cn" "Starting"

  # Build up command options
  local up_opts="-d"
  if [ "$remove_orphans" = true ]; then
    up_opts="$up_opts --remove-orphans"
    echo "[INFO] Will remove orphaned containers"
  fi

  start_infrastructure "$compose_file_args"
  wait_for_postgres "$compose_file_args"

  echo "[INFO] Starting all core services..."
  docker compose --env-file "$ENV_FILE" $compose_file_args up $up_opts

  echo "[INFO] Restarting nginx to pick up new configuration..."
  docker compose --env-file "$ENV_FILE" $compose_file_args restart nginx

  echo "[INFO] All services are starting. Use 'docker compose ps' to inspect status."
}

cmd_down() {
  local remove_volumes=false

  # Parse arguments
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --volumes)
        remove_volumes=true
        shift
        ;;
      *)
        echo "[ERROR] Unknown argument to down: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  ensure_env_files

  # Load saved install mode configuration
  echo "[INFO] Loading saved install mode configuration..."
  local mode="" use_cn=""
  read -r mode use_cn <<< "$(load_install_mode)"

  local compose_file_args
  compose_file_args=$(get_compose_file_args "$mode" "$use_cn") || compose_file_args="-f $MAIN_COMPOSE_IMAGE"
  log_deploy_mode "$mode" "$use_cn" "Stopping"

  if [ "$remove_volumes" = true ]; then
    echo "[INFO] Stopping all services and removing containers and volumes..."
    docker compose --env-file "$ENV_FILE" $compose_file_args down -v
  else
    echo "[INFO] Stopping all services and removing containers (data preserved)..."
    docker compose --env-file "$ENV_FILE" $compose_file_args down
  fi
}

cmd_install() {
  local mode="image"
  local use_cn=false

  # Parse arguments (support --source and --cn in any order)
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source) mode="source"; shift ;;
      --cn) use_cn=true; USE_CN_MIRROR=true; shift ;;
      *) echo "[ERROR] Unknown argument to install: $1" >&2; usage; exit 1 ;;
    esac
  done

  ensure_env_files
  ensure_api_secret_key

  # Check and configure ports (auto-allocate if default ports are occupied)
  check_and_configure_ports || {
    echo "[ERROR] Port configuration failed. Please resolve port conflicts and try again."
    exit 1
  }

  # Configure server host (IP or domain)
  configure_server_host

  # Configure core settings (DB, Redis)
  configure_core_settings

  # Re-source .env to ensure current shell has the updated values before starting docker
  if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi

  # Save install mode for future upgrade commands
  save_install_mode "$mode" "$use_cn"

  local compose_file_args
  compose_file_args=$(get_compose_file_args "$mode" "$use_cn") || exit 1
  log_deploy_mode "$mode" "$use_cn" "Deploying"

  if [ "$mode" = "source" ]; then
    echo "[INFO] Building application images from source..."
    docker compose --env-file "$ENV_FILE" $compose_file_args build
  else
    echo "[INFO] Docker will pull images from $([ "$use_cn" = true ] && echo "Alibaba Cloud ACR" || echo "GHCR")."
  fi

  # Create data directories with correct permissions
  echo "[INFO] Creating data directories..."

  # Determine the target user for directory ownership
  # If running with sudo, use the actual user; otherwise use current user
  if [ -n "${SUDO_USER:-}" ]; then
    TARGET_USER="$SUDO_USER"
    TARGET_UID=$(id -u "$SUDO_USER")
    TARGET_GID=$(id -g "$SUDO_USER")
  else
    TARGET_USER="${USER:-$(whoami)}"
    TARGET_UID=$(id -u)
    TARGET_GID=$(id -g)
  fi

  # List of data directories to create
  DATA_DIRS=(
    "./data/postgres"
    "./data/redis"
    "./data/wukongim"
    "./data/tgo-rag/uploads"
    "./data/tgo-api/uploads"
    "./data/tgo-workflow/uploads"
    "./data/tgo-device-control/screenshots"
    "./data/nginx"
  )

  # Create directories and set permissions
  for dir in "${DATA_DIRS[@]}"; do
    # Determine permission mode - uploads directories need 777 for container access
    local perm_mode="755"
    if [[ "$dir" == *"/uploads" ]]; then
      perm_mode="777"
    fi

    # Check if directory exists and is writable
    if [ -d "$dir" ] && [ -w "$dir" ]; then
      # For uploads directories, ensure they have 777 permissions
      if [[ "$dir" == *"/uploads" ]]; then
        chmod -R 777 "$dir" 2>/dev/null || true
      fi
      echo "  ✓ $dir (already exists and writable)"
      continue
    fi

    # Directory doesn't exist or isn't writable - need to create/fix it
    if [ ! -d "$dir" ]; then
      echo "  Creating $dir..."
      mkdir -p "$dir"

      # Set ownership and permissions only for newly created directories
      if [ "$(id -u)" -eq 0 ] && [ "$TARGET_UID" -ne 0 ]; then
        # Running as root, set to actual user
        chown -R "$TARGET_UID:$TARGET_GID" "$dir"
        chmod -R "$perm_mode" "$dir"
        echo "  Set ownership to $TARGET_USER ($TARGET_UID:$TARGET_GID)"
      elif [ "$(id -u)" -eq 0 ]; then
        # Running as root, set to Docker default user
        chown -R 1000:1000 "$dir"
        chmod -R "$perm_mode" "$dir"
        echo "  Set ownership to 1000:1000 (Docker default)"
      else
        # Running as normal user, just set permissions
        chmod -R "$perm_mode" "$dir" 2>/dev/null || echo "  ⚠ Created but cannot set permissions (may need sudo)"
      fi
    else
      # Directory exists but not writable
      echo "  ⚠ $dir exists but not writable"
      if [ "$(id -u)" -eq 0 ]; then
        # We're root, we can fix it
        chown -R "$TARGET_UID:$TARGET_GID" "$dir" 2>/dev/null || chown -R 1000:1000 "$dir"
        chmod -R "$perm_mode" "$dir"
        echo "  Fixed permissions"
      else
        echo "  ⚠ Run with sudo to fix permissions, or manually run: sudo chown -R \$USER:$TARGET_GID $dir"
      fi
    fi
  done

  echo "[INFO] Data directories created and permissions set."

  # Install WuKongIM plugins (must be present before wukongim container starts)
  install_wukongim_search_plugin

  # Initialize domain configuration and generate Nginx config
  echo "[INFO] Initializing Nginx configuration..."
  ensure_domain_config
  regenerate_nginx_config

  # Start services and run migrations
  echo ""
  echo "[INFO] Starting services..."

  # Determine compose file arguments for service startup
  local compose_file_args
  compose_file_args=$(get_compose_file_args "$mode" "$use_cn") || exit 1

  start_infrastructure "$compose_file_args"
  wait_for_postgres "$compose_file_args"

  # Run database migrations
  run_all_migrations "$compose_file_args"

  # Start all remaining services
  echo "[INFO] Starting all remaining services..."
  docker compose --env-file "$ENV_FILE" $compose_file_args up -d

  # Show installation complete message with access info
  show_install_complete_message
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
      --cn) use_cn=true; USE_CN_MIRROR=true; shift ;;
      *) echo "[ERROR] Unknown argument to uninstall: $1" >&2; usage; exit 1 ;;
    esac
  done

  ensure_env_files

  local compose_file_args
  compose_file_args=$(get_compose_file_args "$mode" "$use_cn") || exit 1
  log_deploy_mode "$mode" "$use_cn" "Uninstalling"

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

cmd_upgrade() {
  local mode=""
  local use_cn=""
  local user_provided_args=false
  local remove_orphans=false

  # Parse command line arguments
  local temp_mode="image"
  local temp_use_cn=false

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source) temp_mode="source"; user_provided_args=true; shift ;;
      --cn) temp_use_cn=true; user_provided_args=true; shift ;;
      --remove-orphans) remove_orphans=true; shift ;;
      *) echo "[ERROR] Unknown argument to upgrade: $1" >&2; usage; exit 1 ;;
    esac
  done

  # If user provided arguments, use them; otherwise load from config
  if [ "$user_provided_args" = true ]; then
    mode="$temp_mode"
    use_cn="$temp_use_cn"
    echo "[INFO] Using user-provided parameters for upgrade"
    save_install_mode "$mode" "$use_cn"
  else
    echo "[INFO] Loading saved install mode configuration..."
    read -r mode use_cn <<< "$(load_install_mode)"
  fi

  [ "$use_cn" = "true" ] && USE_CN_MIRROR=true

  ensure_env_files

  # Determine compose file arguments
  local compose_file_args
  compose_file_args=$(get_compose_file_args "$mode" "$use_cn") || exit 1
  log_deploy_mode "$mode" "$use_cn" "Upgrading"

  # Build up command options
  local up_opts="-d"
  if [ "$remove_orphans" = true ]; then
    up_opts="$up_opts --remove-orphans"
    echo "[INFO] Will remove orphaned containers after upgrade"
  fi

  # Step 0: Pull latest code from git (common for both modes)
  echo ""
  echo "[INFO] Pulling latest code from git..."
  [ "$use_cn" = "true" ] && echo "[INFO] Using Gitee mirrors for git operations"
  
  # Calculate checksum before pull to detect if script itself changes
  local script_path="$0"
  local md5_before=""
  if command -v md5sum >/dev/null 2>&1; then
    md5_before=$(md5sum "$script_path" | cut -d' ' -f1)
  elif command -v md5 >/dev/null 2>&1; then
    md5_before=$(md5 -q "$script_path")
  fi

  git pull || echo "[WARN] git pull failed, continuing with existing code"

  # Check if script itself was updated
  local md5_after=""
  if command -v md5sum >/dev/null 2>&1; then
    md5_after=$(md5sum "$script_path" | cut -d' ' -f1)
  elif command -v md5 >/dev/null 2>&1; then
    md5_after=$(md5 -q "$script_path")
  fi

  if [ -n "$md5_before" ] && [ "$md5_before" != "$md5_after" ]; then
    echo "[INFO] tgo.sh has been updated. Re-executing with the new version..."
    # Preserve all original arguments
    exec bash "$script_path" upgrade "$@"
  fi

  # Update submodules if present
  if [ -f ".gitmodules" ]; then
    echo "[INFO] Updating git submodules..."
    git submodule update --init --recursive || echo "[WARN] Submodule update failed"
  fi

  # Sync new environment variables from .env.example to .env
  echo ""
  echo "[INFO] Checking for new environment variables..."
  if [ -f ".env.example" ] && [ -f "$ENV_FILE" ]; then
    sync_env_file ".env.example" "$ENV_FILE"
  fi

  # Ensure SECRET_KEY is set (generate if missing)
  ensure_api_secret_key

  # Upgrade flow based on mode
  if [ "$mode" = "source" ]; then
    echo ""
    echo "========================================="
    echo "  SOURCE MODE UPGRADE"
    echo "========================================="
    echo ""

    # Step 1: Rebuild images
    echo "[INFO] Step 1/4: Rebuilding Docker images from source..."
    docker compose --env-file "$ENV_FILE" $compose_file_args build

    # Step 2: Stop current services
    echo ""
    echo "[INFO] Step 2/4: Stopping current services..."
    docker compose --env-file "$ENV_FILE" $compose_file_args down

    # Step 3: Start infrastructure and run migrations
    echo ""
    echo "[INFO] Step 3/4: Starting infrastructure services..."
    start_infrastructure "$compose_file_args"
    wait_for_postgres "$compose_file_args"

    # Step 4: Run database migrations
    echo ""
    echo "[INFO] Step 4/4: Running database migrations..."
    run_all_migrations "$compose_file_args"

  else
    echo ""
    echo "========================================="
    echo "  IMAGE MODE UPGRADE"
    echo "========================================="
    echo ""

    # Step 1: Pull latest images
    echo "[INFO] Step 1/4: Pulling latest Docker images..."
    echo "[INFO] Pulling from $([ "$use_cn" = "true" ] && echo "Alibaba Cloud ACR" || echo "GitHub Container Registry")..."
    docker compose --env-file "$ENV_FILE" $compose_file_args pull

    # Step 2: Stop current services
    echo ""
    echo "[INFO] Step 2/4: Stopping current services..."
    docker compose --env-file "$ENV_FILE" $compose_file_args down

    # Step 3: Start infrastructure services
    echo ""
    echo "[INFO] Step 3/4: Starting infrastructure services..."
    start_infrastructure "$compose_file_args"
    wait_for_postgres "$compose_file_args"

    # Step 4: Run database migrations
    echo ""
    echo "[INFO] Step 4/4: Running database migrations..."
    run_all_migrations "$compose_file_args"

    # Start all services (handled below)
  fi

  # Start all services
  echo ""
  echo "[INFO] Starting all services..."
  docker compose --env-file "$ENV_FILE" $compose_file_args up $up_opts

  echo ""
  echo "========================================="
  echo "  ✅ UPGRADE COMPLETE"
  echo "========================================="
  echo ""
  echo "Upgrade summary:"
  echo "  • Mode: $([ "$mode" = "source" ] && echo "SOURCE (built from local code)" || echo "IMAGE (pulled from registry)")"
  echo "  • Registry: $([ "$use_cn" = "true" ] && echo "Alibaba Cloud ACR (China)" || echo "GitHub Container Registry")"
  echo "  • Configuration saved to: $CONFIG_FILE"
  echo ""
  echo "Use 'docker compose ps' to check service status."
  echo "Use 'docker compose logs -f <service>' to view logs."
}

cmd_service() {
  local sub=${1:-}
  shift || true

  local mode="image"
  local use_cn=false

  # Parse arguments (support --source and --cn in any order)
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source) mode="source"; shift ;;
      --cn) use_cn=true; USE_CN_MIRROR=true; shift ;;
      *) echo "[ERROR] Unknown argument to service: $1" >&2; usage; exit 1 ;;
    esac
  done

  ensure_env_files
  local compose_file_args
  compose_file_args=$(get_compose_file_args "$mode" "$use_cn") || exit 1

  case "$sub" in
    start)
      log_deploy_mode "$mode" "$use_cn" "Starting"
      docker compose --env-file "$ENV_FILE" $compose_file_args up -d
      ;;
    stop)
      log_deploy_mode "$mode" "$use_cn" "Stopping"
      docker compose --env-file "$ENV_FILE" $compose_file_args down
      ;;
    remove)
      log_deploy_mode "$mode" "$use_cn" "Removing"
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
      echo "[INFO] Starting debug tools (adminer, redis-insight)..."
      docker compose -f "$TOOLS_COMPOSE" up -d
      ;;
    stop)
      echo "[INFO] Stopping debug tools (adminer, redis-insight)..."
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

  local mode="source"
  local use_cn=false

  # Parse arguments (support --source and --cn in any order)
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --source)
        # Deprecated: build always uses source mode; this flag is no longer required.
        shift
        ;;
      --cn)
        # Deprecated: build always uses source mode and does not need --cn.
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
    rag) services=(tgo-rag tgo-rag-worker tgo-rag-beat) ;;
    workflow) services=(tgo-workflow tgo-workflow-worker) ;;
    ai) services=(tgo-ai) ;;
    plugin-runtime) services=(tgo-plugin-runtime) ;;
    device-control) services=(tgo-device-control) ;;
    platform) services=(tgo-platform) ;;
    celery) services=(tgo-celery-flower) ;;
    web) services=(tgo-web) ;;
    widget) services=(tgo-widget-app) ;;
    all) services=() ;;
    *)
      echo "[ERROR] Unknown service: $target" >&2
      echo "Supported: api, rag, ai, plugin-runtime, device-control, workflow, platform, web, widget, all" >&2
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
    
    # Run all migrations for all services
    echo "[INFO] Running database migrations..."
    wait_for_postgres "$compose_file_args"
    run_all_migrations "$compose_file_args"
    
    docker compose --env-file "$ENV_FILE" $compose_file_args up -d
  else
    echo "[INFO] Rebuilding services from source: ${services[*]}..."
    docker compose --env-file "$ENV_FILE" $compose_file_args build "${services[@]}"
    
    # Run migrations for the specific service if applicable
    run_service_migrations "$target" "$compose_file_args"
    
    docker compose --env-file "$ENV_FILE" $compose_file_args up -d "${services[@]}"
  fi
}

# Run migrations for a specific service
# Usage: run_service_migrations <service_target> <compose_file_args>
run_service_migrations() {
  local target="$1"
  local compose_file_args="$2"
  
  # Only run migrations for services that have Alembic
  case "$target" in
    api)
      echo "[INFO] Running Alembic migrations for tgo-api..."
      wait_for_postgres "$compose_file_args"
      docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-api alembic upgrade head
      ;;
    rag)
      echo "[INFO] Running Alembic migrations for tgo-rag..."
      wait_for_postgres "$compose_file_args"
      docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-rag alembic upgrade head
      ;;
    ai)
      echo "[INFO] Running Alembic migrations for tgo-ai..."
      wait_for_postgres "$compose_file_args"
      docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-ai alembic upgrade head
      ;;
    workflow)
      echo "[INFO] Running Alembic migrations for tgo-workflow..."
      wait_for_postgres "$compose_file_args"
      docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-workflow alembic upgrade head
      ;;
    platform)
      echo "[INFO] Running Alembic migrations for tgo-platform..."
      wait_for_postgres "$compose_file_args"
      docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T -e PYTHONPATH=. tgo-platform alembic upgrade head
      ;;
    plugin-runtime)
      echo "[INFO] Running Alembic migrations for tgo-plugin-runtime..."
      wait_for_postgres "$compose_file_args"
      docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-plugin-runtime alembic upgrade head
      ;;
    device-control)
      echo "[INFO] Running Alembic migrations for tgo-device-control..."
      wait_for_postgres "$compose_file_args"
      docker compose --env-file "$ENV_FILE" $compose_file_args run --rm -T tgo-device-control alembic upgrade head
      ;;
    web|widget)
      # Frontend services don't have database migrations
      echo "[INFO] No database migrations needed for $target"
      ;;
    *)
      echo "[WARN] Unknown service target for migrations: $target"
      ;;
  esac
}

# Helper function to get protocol based on SSL mode
get_protocol_for_ssl_mode() {
  local ssl_mode="${1:-none}"
  if [ "$ssl_mode" = "none" ]; then
    echo "http"
  else
    echo "https"
  fi
}

# Helper function to update domain-related environment variables
update_domain_env_vars() {
  local domain_config_file="./data/.tgo-domain-config"

  # Load current domain configuration
  local ssl_mode="none"
  local web_domain=""
  local widget_domain=""
  local api_domain=""
  local ws_domain=""

  if [ -f "$domain_config_file" ]; then
    ssl_mode=$(grep -E "^SSL_MODE=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "none")
    web_domain=$(grep -E "^WEB_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
    widget_domain=$(grep -E "^WIDGET_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
    api_domain=$(grep -E "^API_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
    ws_domain=$(grep -E "^WS_DOMAIN=" "$domain_config_file" 2>/dev/null | cut -d= -f2- || echo "")
  fi

  ssl_mode="${ssl_mode:-none}"
  local protocol
  protocol=$(get_protocol_for_ssl_mode "$ssl_mode")

  # Update API domain related env vars
  if [ -n "$api_domain" ] && [ "$api_domain" != "localhost" ]; then
    update_env_var "VITE_API_BASE_URL" "${protocol}://${api_domain}"
    echo "[INFO] Updated VITE_API_BASE_URL=${protocol}://${api_domain}"
  fi

  # Update Widget domain related env vars
  if [ -n "$widget_domain" ] && [ "$widget_domain" != "localhost" ]; then
    update_env_var "VITE_WIDGET_PREVIEW_URL" "${protocol}://${widget_domain}"
    update_env_var "VITE_WIDGET_SCRIPT_BASE" "${protocol}://${widget_domain}/tgo-widget-sdk.js"
    update_env_var "VITE_WIDGET_DEMO_URL" "${protocol}://${widget_domain}/demo.html"
    echo "[INFO] Updated VITE_WIDGET_PREVIEW_URL=${protocol}://${widget_domain}"
    echo "[INFO] Updated VITE_WIDGET_SCRIPT_BASE=${protocol}://${widget_domain}/tgo-widget-sdk.js"
    echo "[INFO] Updated VITE_WIDGET_DEMO_URL=${protocol}://${widget_domain}/demo.html"
  fi

  # Update WuKongIM WebSocket domain related env vars
  if [ -n "$ws_domain" ] && [ "$ws_domain" != "localhost" ]; then
    if [ "$ssl_mode" = "none" ]; then
      update_env_var "WK_EXTERNAL_WSADDR" "ws://${ws_domain}"
      update_env_var "WK_EXTERNAL_WSSADDR" ""
      echo "[INFO] Updated WK_EXTERNAL_WSADDR=ws://${ws_domain}"
    else
      update_env_var "WK_EXTERNAL_WSADDR" ""
      update_env_var "WK_EXTERNAL_WSSADDR" "wss://${ws_domain}"
      echo "[INFO] Updated WK_EXTERNAL_WSSADDR=wss://${ws_domain}"
    fi
  fi

  # Update Web domain related env vars (if any needed in the future)
  # Currently no VITE_* vars depend on web_domain
}

cmd_config() {
  local domain_config_file="./data/.tgo-domain-config"
  local subcommand=${1:-show}
  shift || true

  # Ensure data directory exists
  mkdir -p "$(dirname "$domain_config_file")"

  case "$subcommand" in
    web_domain)
      if [ $# -eq 0 ]; then
        echo "[ERROR] Domain value required"
        exit 1
      fi
      local domain="$1"
      ensure_domain_config
      sed -i.bak "s|^WEB_DOMAIN=.*|WEB_DOMAIN=$domain|" "$domain_config_file"
      rm -f "$domain_config_file.bak"
      echo "[INFO] Web domain set to: $domain"
      update_domain_env_vars
      regenerate_nginx_config
      ;;
    widget_domain)
      if [ $# -eq 0 ]; then
        echo "[ERROR] Domain value required"
        exit 1
      fi
      local domain="$1"
      ensure_domain_config
      sed -i.bak "s|^WIDGET_DOMAIN=.*|WIDGET_DOMAIN=$domain|" "$domain_config_file"
      rm -f "$domain_config_file.bak"
      echo "[INFO] Widget domain set to: $domain"
      update_domain_env_vars
      regenerate_nginx_config
      ;;
    api_domain)
      if [ $# -eq 0 ]; then
        echo "[ERROR] Domain value required"
        exit 1
      fi
      local domain="$1"
      ensure_domain_config
      sed -i.bak "s|^API_DOMAIN=.*|API_DOMAIN=$domain|" "$domain_config_file"
      rm -f "$domain_config_file.bak"
      echo "[INFO] API domain set to: $domain"
      update_domain_env_vars
      regenerate_nginx_config
      ;;
    ws_domain)
      if [ $# -eq 0 ]; then
        echo "[ERROR] Domain value required"
        exit 1
      fi
      local domain="$1"
      ensure_domain_config
      sed -i.bak "s|^WS_DOMAIN=.*|WS_DOMAIN=$domain|" "$domain_config_file"
      rm -f "$domain_config_file.bak"
      echo "[INFO] WebSocket domain set to: $domain"
      update_domain_env_vars
      regenerate_nginx_config
      ;;
    http_port)
      if [ $# -eq 0 ]; then
        echo "[ERROR] Port value required"
        exit 1
      fi
      local port="$1"
      update_env_var "NGINX_PORT" "$port"
      echo "[INFO] HTTP port set to: $port"
      
      # Re-sync frontend URLs if SERVER_HOST exists
      local current_host
      current_host=$(grep -E "^SERVER_HOST=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "")
      if [ -n "$current_host" ]; then
        update_frontend_urls "$current_host"
      fi
      ;;
    https_port)
      if [ $# -eq 0 ]; then
        echo "[ERROR] Port value required"
        exit 1
      fi
      local port="$1"
      update_env_var "NGINX_SSL_PORT" "$port"
      echo "[INFO] HTTPS port set to: $port"
      ;;
    ssl_mode)
      if [ $# -eq 0 ]; then
        echo "[ERROR] SSL mode required (auto|manual|none)"
        exit 1
      fi
      local mode="$1"
      if [[ ! "$mode" =~ ^(auto|manual|none)$ ]]; then
        echo "[ERROR] Invalid SSL mode: $mode (must be auto, manual, or none)"
        exit 1
      fi
      ensure_domain_config
      sed -i.bak "s|^SSL_MODE=.*|SSL_MODE=$mode|" "$domain_config_file"
      rm -f "$domain_config_file.bak"
      echo "[INFO] SSL mode set to: $mode"
      # Update all domain env vars with new protocol
      update_domain_env_vars
      regenerate_nginx_config
      ;;
    ssl_email)
      if [ $# -eq 0 ]; then
        echo "[ERROR] Email value required"
        exit 1
      fi
      local email="$1"
      ensure_domain_config
      sed -i.bak "s|^SSL_EMAIL=.*|SSL_EMAIL=$email|" "$domain_config_file"
      rm -f "$domain_config_file.bak"
      echo "[INFO] SSL email set to: $email"
      ;;
    ssl_manual)
      if [ $# -lt 2 ]; then
        echo "[ERROR] Usage: ./tgo.sh config ssl_manual <cert_file> <key_file> [domain]"
        exit 1
      fi
      local cert_file="$1"
      local key_file="$2"
      local domain="${3:-}"

      if [ ! -f "$cert_file" ] || [ ! -f "$key_file" ]; then
        echo "[ERROR] Certificate or key file not found"
        exit 1
      fi

      ensure_domain_config

      # If domain not specified, use all configured domains
      if [ -z "$domain" ]; then
        source "$domain_config_file" 2>/dev/null || true
        for d in "$WEB_DOMAIN" "$WIDGET_DOMAIN" "$API_DOMAIN"; do
          [ -z "$d" ] && continue
          copy_manual_cert "$cert_file" "$key_file" "$d"
        done
      else
        copy_manual_cert "$cert_file" "$key_file" "$domain"
      fi

      sed -i.bak "s/^SSL_MODE=.*/SSL_MODE=manual/" "$domain_config_file"
      echo "[INFO] Manual SSL certificates installed"
      ;;
    setup_letsencrypt)
      ensure_domain_config
      source "$domain_config_file" 2>/dev/null || true

      if [ -z "$WEB_DOMAIN" ] || [ -z "$WIDGET_DOMAIN" ] || [ -z "$API_DOMAIN" ]; then
        echo "[ERROR] All domains must be configured first"
        echo "[INFO] Run: ./tgo.sh config web_domain <domain>"
        exit 1
      fi

      local email="${SSL_EMAIL:-admin@example.com}"
      local ws_domain="${WS_DOMAIN:-}"
      echo "[INFO] Setting up Let's Encrypt certificates..."
      bash ./scripts/setup-ssl.sh "$WEB_DOMAIN" "$WIDGET_DOMAIN" "$API_DOMAIN" "$email" "$ws_domain"

      sed -i.bak "s|^SSL_MODE=.*|SSL_MODE=auto|" "$domain_config_file"
      rm -f "$domain_config_file.bak"
      echo "[INFO] SSL mode set to: auto"
      # Update env vars with new SSL mode
      update_domain_env_vars
      ;;
    apply)
      if [ ! -f "$domain_config_file" ]; then
        echo "[ERROR] No domain configuration found"
        exit 1
      fi
      
      echo "[INFO] Regenerating Nginx configuration..."
      regenerate_nginx_config
      
      # Update environment variables based on domain config
      echo "[INFO] Updating environment variables..."
      update_domain_env_vars
      
      # Load saved install mode configuration to determine compose files
      ensure_env_files
      local mode=""
      local use_cn=""
      read -r mode use_cn <<< "$(load_install_mode)"
      
      local compose_file_args="-f $MAIN_COMPOSE_IMAGE"
      if [ "$mode" = "source" ]; then
        if [ -f "$MAIN_COMPOSE_SOURCE" ]; then
          compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_SOURCE"
        fi
      elif [ "$use_cn" = "true" ]; then
        if [ -f "$MAIN_COMPOSE_CN" ]; then
          compose_file_args="-f $MAIN_COMPOSE_IMAGE -f $MAIN_COMPOSE_CN"
        fi
      fi
      
      # Check if services are running
      if docker compose --env-file "$ENV_FILE" $compose_file_args ps --quiet 2>/dev/null | grep -q .; then
        echo "[INFO] Restarting services to apply configuration changes..."
        
        # Recreate services with updated .env (for VITE_* variables)
        docker compose --env-file "$ENV_FILE" $compose_file_args up -d
        
        # Restart nginx to pick up new configuration
        echo "[INFO] Restarting Nginx..."
        docker compose --env-file "$ENV_FILE" $compose_file_args restart nginx
        
        echo "[INFO] Configuration applied and services restarted"
      else
        echo "[INFO] Services are not running. Configuration will be applied on next start."
        echo "[INFO] Run './tgo.sh up' to start services with new configuration."
      fi
      ;;
    show)
      if [ ! -f "$domain_config_file" ]; then
        echo "[INFO] No domain configuration found"
        echo "[INFO] Run: ./tgo.sh config web_domain <domain> to get started"
        exit 0
      fi
      echo "[INFO] Current domain configuration:"
      cat "$domain_config_file"
      ;;
    *)
      echo "[ERROR] Unknown config subcommand: $subcommand"
      echo "Usage: ./tgo.sh config <subcommand> [args]"
      echo ""
      echo "Subcommands:"
      echo "  web_domain <domain>           Set web service domain"
      echo "  widget_domain <domain>        Set widget service domain"
      echo "  api_domain <domain>           Set API service domain"
      echo "  ws_domain <domain>            Set WebSocket service domain (WuKongIM)"
      echo "  http_port <port>              Set Nginx HTTP port"
      echo "  https_port <port>             Set Nginx HTTPS port"
      echo "  ssl_mode <auto|manual|none>   Set SSL mode"
      echo "  ssl_email <email>             Set Let's Encrypt email"
      echo "  ssl_manual <cert> <key> [domain]  Install manual SSL certificate"
      echo "  setup_letsencrypt             Setup Let's Encrypt certificates"
      echo "  apply                         Regenerate Nginx configuration"
      echo "  show                          Show current configuration"
      exit 1
      ;;
  esac
}

# Helper function to ensure domain config file exists
ensure_domain_config() {
  local domain_config_file="./data/.tgo-domain-config"
  if [ ! -f "$domain_config_file" ]; then
    cat > "$domain_config_file" << 'EOF'
# TGO Domain Configuration
# Auto-generated by ./tgo.sh config

WEB_DOMAIN=
WIDGET_DOMAIN=
API_DOMAIN=
WS_DOMAIN=
SSL_MODE=none
SSL_EMAIL=
ENABLE_SSL_AUTO_RENEW=true
EOF
    echo "[INFO] Created domain configuration file: $domain_config_file"
  else
    # Ensure WS_DOMAIN exists in config file (for upgrades)
    if ! grep -q "^WS_DOMAIN=" "$domain_config_file" 2>/dev/null; then
      echo "WS_DOMAIN=" >> "$domain_config_file"
    fi
  fi
}

# Helper function to copy manual SSL certificates
copy_manual_cert() {
  local cert_file="$1"
  local key_file="$2"
  local domain="$3"

  local ssl_dir="./data/nginx/ssl/$domain"
  mkdir -p "$ssl_dir"

  cp "$cert_file" "$ssl_dir/cert.pem"
  cp "$key_file" "$ssl_dir/key.pem"

  echo "[INFO] Certificate installed for: $domain"
}

# Helper function to regenerate Nginx configuration
regenerate_nginx_config() {
  if [ ! -f "./scripts/generate-nginx-config.sh" ]; then
    echo "[WARN] Nginx config generator not found"
    return
  fi

  bash ./scripts/generate-nginx-config.sh || {
    echo "[WARN] Failed to regenerate Nginx configuration"
  }
}

# Doctor command - check health status of all services
cmd_doctor() {
  echo ""
  echo "========================================="
  echo "  TGO Health Check"
  echo "========================================="
  echo ""
  
  local all_healthy=true
  local total_services=0
  local healthy_services=0
  local unhealthy_services=0
  
  # Define services to check
  local services=(
    "tgo-postgres:PostgreSQL"
    "tgo-redis:Redis"
    "tgo-wukongim:WuKongIM"
    "tgo-rag:RAG Service"
    "tgo-rag-worker:RAG Worker"
    "tgo-rag-beat:RAG Beat"
    "tgo-celery-flower:Celery Flower"
    "tgo-ai:AI Service"
    "tgo-plugin-runtime:Plugin Runtime"
    "tgo-device-control:Device Control"
    "tgo-workflow:Workflow Service"
    "tgo-workflow-worker:Workflow Worker"
    "tgo-api:API Service"
    "tgo-platform:Platform Service"
    "tgo-web:Web Frontend"
    "tgo-widget-app:Widget App"
    "tgo-nginx:Nginx"
  )
  
  echo "Checking services..."
  echo ""
  
  for service_info in "${services[@]}"; do
    local container_name="${service_info%%:*}"
    local display_name="${service_info##*:}"
    total_services=$((total_services + 1))
    
    # Check if container exists and is running
    local status
    status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "not_found")
    
    local health=""
    if [ "$status" = "running" ]; then
      # Check health status if available
      health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no_healthcheck{{end}}' "$container_name" 2>/dev/null || echo "unknown")
    fi
    
    # Determine status icon and message
    local icon=""
    local status_msg=""
    
    case "$status" in
      running)
        case "$health" in
          healthy)
            icon="✅"
            status_msg="running (healthy)"
            healthy_services=$((healthy_services + 1))
            ;;
          unhealthy)
            icon="❌"
            status_msg="running (unhealthy)"
            unhealthy_services=$((unhealthy_services + 1))
            all_healthy=false
            ;;
          starting)
            icon="🔄"
            status_msg="running (starting)"
            healthy_services=$((healthy_services + 1))
            ;;
          no_healthcheck)
            icon="✅"
            status_msg="running"
            healthy_services=$((healthy_services + 1))
            ;;
          *)
            icon="⚠️"
            status_msg="running ($health)"
            healthy_services=$((healthy_services + 1))
            ;;
        esac
        ;;
      exited)
        icon="❌"
        status_msg="exited"
        unhealthy_services=$((unhealthy_services + 1))
        all_healthy=false
        ;;
      restarting)
        icon="🔄"
        status_msg="restarting"
        unhealthy_services=$((unhealthy_services + 1))
        all_healthy=false
        ;;
      not_found)
        icon="⚪"
        status_msg="not running"
        unhealthy_services=$((unhealthy_services + 1))
        all_healthy=false
        ;;
      *)
        icon="⚠️"
        status_msg="$status"
        unhealthy_services=$((unhealthy_services + 1))
        all_healthy=false
        ;;
    esac
    
    printf "  %s %-20s %s\n" "$icon" "$display_name" "$status_msg"
  done
  
  echo ""
  echo "-----------------------------------------"
  echo "Summary: $healthy_services/$total_services services healthy"
  echo ""
  
  # Additional checks
  echo "Additional checks:"
  echo ""
  
  # Check .env file
  if [ -f "$ENV_FILE" ]; then
    local server_host
    server_host=$(grep -E "^SERVER_HOST=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "")
    if [ -n "$server_host" ]; then
      echo "  ✅ SERVER_HOST configured: $server_host"
    else
      echo "  ⚠️  SERVER_HOST not configured in .env"
    fi
  else
    echo "  ❌ .env file not found"
    all_healthy=false
  fi
  
  # Check nginx config
  if [ -f "./data/nginx/conf.d/default.conf" ]; then
    echo "  ✅ Nginx configuration exists"
  else
    echo "  ⚠️  Nginx configuration not found"
  fi
  
  # Check data directories
  local data_dirs_ok=true
  for dir in "./data/postgres" "./data/redis" "./data/wukongim"; do
    if [ ! -d "$dir" ]; then
      data_dirs_ok=false
      break
    fi
  done
  if [ "$data_dirs_ok" = true ]; then
    echo "  ✅ Data directories exist"
  else
    echo "  ⚠️  Some data directories missing"
  fi
  
  # Test API endpoint
  local server_host
  server_host=$(grep -E "^SERVER_HOST=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo "localhost")
  server_host="${server_host:-localhost}"
  
  if command -v curl >/dev/null 2>&1; then
    local api_response
    api_response=$(curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" "http://${server_host}/api/health" 2>/dev/null || echo "000")
    if [ "$api_response" = "200" ]; then
      echo "  ✅ API endpoint responding (HTTP $api_response)"
    elif [ "$api_response" = "000" ]; then
      echo "  ⚠️  API endpoint not reachable"
    else
      echo "  ⚠️  API endpoint returned HTTP $api_response"
    fi
  fi
  
  # Test Web endpoint
  if command -v curl >/dev/null 2>&1; then
    local web_response
    web_response=$(curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" "http://${server_host}/" 2>/dev/null || echo "000")
    if [ "$web_response" = "200" ]; then
      echo "  ✅ Web console responding (HTTP $web_response)"
    elif [ "$web_response" = "000" ]; then
      echo "  ⚠️  Web console not reachable"
    else
      echo "  ⚠️  Web console returned HTTP $web_response"
    fi
  fi
  
  echo ""
  
  # Final status
  if [ "$all_healthy" = true ]; then
    echo "========================================="
    echo "  ✅ All services are healthy!"
    echo "========================================="
    echo ""
    return 0
  else
    echo "========================================="
    echo "  ⚠️  Some services need attention"
    echo "========================================="
    echo ""
    echo "Troubleshooting tips:"
    echo "  • View logs:      docker compose logs -f <service>"
    echo "  • Restart all:    ./tgo.sh down && ./tgo.sh up"
    echo "  • Check status:   docker compose ps"
    echo ""
    return 1
  fi
}

main() {
  local cmd=${1:-help}
  shift || true
  case "$cmd" in
    help|-h|--help) usage ;;
    install) cmd_install "$@" ;;
    up) cmd_up "$@" ;;
    down) cmd_down "$@" ;;
    upgrade) cmd_upgrade "$@" ;;
    uninstall) cmd_uninstall "$@" ;;
    doctor) cmd_doctor "$@" ;;
    service) cmd_service "$@" ;;
    tools) cmd_tools "$@" ;;
    build) cmd_build "$@" ;;
    config) cmd_config "$@" ;;
    *)
      echo "[ERROR] Unknown command: $cmd" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"

