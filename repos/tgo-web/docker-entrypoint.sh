#!/bin/sh
# Docker entrypoint script for tgo-web
# Generates runtime configuration from environment variables
# This allows configuration changes without rebuilding the application

set -e

# Configuration file path
CONFIG_FILE="/usr/share/nginx/html/env-config.js"

# Get environment variables with defaults
VITE_API_BASE_URL="${VITE_API_BASE_URL:-/api}"
VITE_DEBUG_MODE="${VITE_DEBUG_MODE:-false}"
VITE_WIDGET_PREVIEW_URL="${VITE_WIDGET_PREVIEW_URL:-/widget}"
VITE_WIDGET_SCRIPT_BASE="${VITE_WIDGET_SCRIPT_BASE:-}"
VITE_WIDGET_DEMO_URL="${VITE_WIDGET_DEMO_URL:-}"
VITE_DISABLE_WEBSOCKET_AUTO_CONNECT="${VITE_DISABLE_WEBSOCKET_AUTO_CONNECT:-false}"
VITE_STORE_API_URL="${VITE_STORE_API_URL:-/store-api/api/v1}"

# Generate env-config.js with runtime configuration
cat > "$CONFIG_FILE" << EOF
// Runtime environment configuration for tgo-web
// Generated at container startup from environment variables
// Priority: window.ENV (runtime) > import.meta.env (build-time) > defaults
window.ENV = {
  VITE_API_BASE_URL: '$VITE_API_BASE_URL',
  VITE_DEBUG_MODE: $VITE_DEBUG_MODE,
  VITE_WIDGET_PREVIEW_URL: '$VITE_WIDGET_PREVIEW_URL',
  VITE_WIDGET_SCRIPT_BASE: '$VITE_WIDGET_SCRIPT_BASE',
  VITE_WIDGET_DEMO_URL: '$VITE_WIDGET_DEMO_URL',
  VITE_DISABLE_WEBSOCKET_AUTO_CONNECT: '$VITE_DISABLE_WEBSOCKET_AUTO_CONNECT',
  VITE_STORE_API_URL: '$VITE_STORE_API_URL',
};
EOF

echo "[INFO] Generated runtime configuration:"
echo "[INFO]   VITE_API_BASE_URL: $VITE_API_BASE_URL"
echo "[INFO]   VITE_DEBUG_MODE: $VITE_DEBUG_MODE"
echo "[INFO]   VITE_WIDGET_PREVIEW_URL: $VITE_WIDGET_PREVIEW_URL"
echo "[INFO]   VITE_WIDGET_SCRIPT_BASE: $VITE_WIDGET_SCRIPT_BASE"
echo "[INFO]   VITE_WIDGET_DEMO_URL: $VITE_WIDGET_DEMO_URL"
echo "[INFO]   VITE_DISABLE_WEBSOCKET_AUTO_CONNECT: $VITE_DISABLE_WEBSOCKET_AUTO_CONNECT"
echo "[INFO]   VITE_STORE_API_URL: $VITE_STORE_API_URL"

# Start Nginx
exec nginx -g "daemon off;"
