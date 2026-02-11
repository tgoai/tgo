# syntax=docker/dockerfile:1.7
# TGO Web (React + Vite) - build and serve via Nginx
#
# Runtime Configuration:
# All VITE_* environment variables are configured at runtime, not build time.
# Set these environment variables when running the container:
#   - VITE_API_BASE_URL: Backend API URL (default: /api)
#   - VITE_DEBUG_MODE: Enable debug mode (default: false)
#   - VITE_WIDGET_PREVIEW_URL: Widget preview URL (default: /widget)
#   - VITE_WIDGET_SCRIPT_BASE: Widget SDK script URL
#   - VITE_WIDGET_DEMO_URL: Widget demo page URL
#   - VITE_DISABLE_WEBSOCKET_AUTO_CONNECT: Disable WebSocket auto-connect (default: false)
#
# Example:
#   docker run -e VITE_API_BASE_URL=https://api.example.com -p 80:80 tgo-web

# --- Build stage ---
ARG BUILDPLATFORM=linux/amd64
FROM --platform=$BUILDPLATFORM node:20-alpine AS builder
WORKDIR /app
ENV CI=true

# Install deps
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --non-interactive --network-timeout 600000

# Build (no VITE_* variables needed at build time - they're configured at runtime)
COPY . .
RUN yarn build

# --- Runtime stage ---
FROM nginx:alpine

# Optional: healthcheck dependency
RUN apk add --no-cache curl

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy entrypoint script (generates runtime config from environment variables)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Copy nginx config (SPA fallback + real IP forwarding)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD curl -f http://localhost/ || exit 1

# Use entrypoint script to generate runtime config and start Nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
