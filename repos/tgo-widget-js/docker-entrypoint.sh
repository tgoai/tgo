#!/bin/sh
# Docker entrypoint script for tgo-widget-js
# Generates runtime configuration from environment variables

set -e

# Configuration file path
CONFIG_FILE="/usr/share/nginx/html/env-config.js"

# Get environment variables with defaults
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8000}"

# Generate env-config.js with runtime configuration
cat > "$CONFIG_FILE" << EOF
// Runtime environment configuration for tgo-widget-js
// Generated at container startup from environment variables
window.ENV = {
  VITE_API_BASE_URL: '$VITE_API_BASE_URL',
};
EOF

echo "[INFO] Generated runtime configuration:"
echo "[INFO]   VITE_API_BASE_URL: $VITE_API_BASE_URL"

# Start Nginx
exec nginx -g "daemon off;"

