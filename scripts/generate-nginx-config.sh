#!/bin/bash
# Generate Nginx configuration based on domain and SSL settings
# Usage: ./scripts/generate-nginx-config.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/data/.tgo-domain-config"
NGINX_CONF_DIR="$PROJECT_ROOT/data/nginx/conf.d"

# Load domain configuration
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[WARN] Domain configuration not found: $CONFIG_FILE"
    echo "[INFO] Using default localhost configuration"
    # Set defaults for localhost
    WEB_DOMAIN=""
    WIDGET_DOMAIN=""
    API_DOMAIN=""
    SSL_MODE="none"
else
    source "$CONFIG_FILE"
fi

# Ensure nginx conf directory exists
mkdir -p "$NGINX_CONF_DIR"

# Determine SSL configuration
SSL_ENABLED=${SSL_MODE:-none}
WEB_DOMAIN=${WEB_DOMAIN:-localhost}
WIDGET_DOMAIN=${WIDGET_DOMAIN:-localhost}
API_DOMAIN=${API_DOMAIN:-localhost}

# Generate nginx configuration
cat > "$NGINX_CONF_DIR/default.conf" << 'NGINX_CONFIG'
# Shared routing helpers
# DNS resolver for dynamic upstreams (Docker internal DNS)
resolver 127.0.0.11 ipv6=off;
# Decide which upstream (web vs widget) should serve frontend traffic based on Referer
map $http_referer $assets_upstream {
    ~*/widget(/|$)  tgo-widget-app:80;
    default          tgo-web:80;
}

# HTTP server block - redirect to HTTPS or serve directly
server {
    listen 80;
    server_name _;

    # Allow Let's Encrypt ACME challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
NGINX_CONFIG

if [ "$SSL_ENABLED" != "none" ]; then
    cat >> "$NGINX_CONF_DIR/default.conf" << 'NGINX_CONFIG'

    # Redirect to HTTPS if SSL is enabled
    location / {
        return 301 https://$server_name$request_uri;
    }
}
NGINX_CONFIG
else
    cat >> "$NGINX_CONF_DIR/default.conf" << 'NGINX_CONFIG'

    # API service (by domain or /api path)
    # Strip /api prefix when forwarding to backend
    location ~ ^/api(/|$) {
        rewrite ^/api(/.*)$ $1 break;
        proxy_pass http://tgo-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Widget service (by domain or /widget path)
    # Strip /widget prefix when forwarding to backend
    location ~ ^/widget(/|$) {
        rewrite ^/widget(/.*)$ $1 break;
        proxy_pass http://tgo-widget-app:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Static assets for web and widget apps
    # Decide upstream (tgo-web vs tgo-widget-app) based on Referer
    location /assets/ {
        proxy_pass http://$assets_upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Web / widget HTML and other resources (root path)
    # Choose upstream (tgo-web or tgo-widget-app) based on Referer
    location / {
        proxy_pass http://$assets_upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
NGINX_CONFIG
fi

# Add HTTPS server blocks if SSL is enabled
if [ "$SSL_ENABLED" != "none" ]; then
    cat >> "$NGINX_CONF_DIR/default.conf" << 'NGINX_CONFIG'

# HTTPS - Web Service
server {
    listen 443 ssl http2;
    server_name WEB_DOMAIN;

    ssl_certificate /etc/nginx/ssl/WEB_DOMAIN/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/WEB_DOMAIN/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://tgo-web:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}

# HTTPS - Widget Service
server {
    listen 443 ssl http2;
    server_name WIDGET_DOMAIN;

    ssl_certificate /etc/nginx/ssl/WIDGET_DOMAIN/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/WIDGET_DOMAIN/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://tgo-widget-app:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}

# HTTPS - API Service
server {
    listen 443 ssl http2;
    server_name API_DOMAIN;

    ssl_certificate /etc/nginx/ssl/API_DOMAIN/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/API_DOMAIN/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://tgo-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}

# HTTPS - Unified server block (for localhost or when domains are not configured)
server {
    listen 443 ssl http2;
    server_name localhost;

    ssl_certificate /etc/nginx/ssl/localhost/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/localhost/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # API service (by /api path)
    # Strip /api prefix when forwarding to backend
    location ~ ^/api(/|$) {
        rewrite ^/api(/.*)$ $1 break;
        proxy_pass http://tgo-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Widget service (by /widget path)
    # Strip /widget prefix when forwarding to backend
    location ~ ^/widget(/|$) {
        rewrite ^/widget(/.*)$ $1 break;
        proxy_pass http://tgo-widget-app:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Web service (default, root path)
    location / {
        proxy_pass http://tgo-web:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
NGINX_CONFIG
fi

# Replace domain placeholders using a temporary file to avoid sed issues
TEMP_CONF=$(mktemp)
cat "$NGINX_CONF_DIR/default.conf" | sed "s/WEB_DOMAIN/$WEB_DOMAIN/g" | \
  sed "s/WIDGET_DOMAIN/$WIDGET_DOMAIN/g" | \
  sed "s/API_DOMAIN/$API_DOMAIN/g" > "$TEMP_CONF"
mv "$TEMP_CONF" "$NGINX_CONF_DIR/default.conf"

echo "[INFO] Nginx configuration generated: $NGINX_CONF_DIR/default.conf"
echo "[INFO] Domains configured:"
echo "  - Web: $WEB_DOMAIN"
echo "  - Widget: $WIDGET_DOMAIN"
echo "  - API: $API_DOMAIN"
echo "[INFO] SSL Mode: $SSL_ENABLED"

