#!/bin/sh
# Docker entrypoint script for tgo-widget-app
# Generates runtime configuration from environment variables

set -e

# Configuration file path
CONFIG_FILE="/usr/share/nginx/html/env-config.js"

# Get environment variables with defaults
VITE_API_BASE="${VITE_API_BASE:-http://localhost:8000}"

# Generate env-config.js with runtime configuration
cat > "$CONFIG_FILE" << EOF
// Runtime environment configuration for tgo-widget-app
// Generated at container startup from environment variables
window.ENV = {
  VITE_API_BASE: '$VITE_API_BASE',
};
EOF

echo "[INFO] Generated runtime configuration:"
echo "[INFO]   VITE_API_BASE: $VITE_API_BASE"

# Start Nginx
exec nginx -g "daemon off;"

