#!/bin/sh
# Docker entrypoint script for tgo-web
# Generates runtime configuration from environment variables

set -e

# Configuration file path
CONFIG_FILE="/usr/share/nginx/html/env-config.js"

# Get environment variables with defaults
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8000}"
VITE_DEBUG_MODE="${VITE_DEBUG_MODE:-false}"
VITE_WIDGET_PREVIEW_URL="${VITE_WIDGET_PREVIEW_URL:-http://localhost/widget}"

# Generate env-config.js with runtime configuration
cat > "$CONFIG_FILE" << EOF
// Runtime environment configuration for tgo-web
// Generated at container startup from environment variables
window.ENV = {
  VITE_API_BASE_URL: '$VITE_API_BASE_URL',
  VITE_DEBUG_MODE: $VITE_DEBUG_MODE,
  VITE_WIDGET_PREVIEW_URL: '$VITE_WIDGET_PREVIEW_URL',
};
EOF

echo "[INFO] Generated runtime configuration:"
echo "[INFO]   VITE_API_BASE_URL: $VITE_API_BASE_URL"
echo "[INFO]   VITE_DEBUG_MODE: $VITE_DEBUG_MODE"
echo "[INFO]   VITE_WIDGET_PREVIEW_URL: $VITE_WIDGET_PREVIEW_URL"

# Start Nginx
exec nginx -g "daemon off;"

