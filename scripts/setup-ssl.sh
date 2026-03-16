#!/bin/bash
# Setup SSL certificates for Let's Encrypt
# Usage: ./scripts/setup-ssl.sh <domain1> <domain2> <domain3> [email] [ws_domain]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/data/.tgo-domain-config"
CERTBOT_DIR="$PROJECT_ROOT/data/certbot"
SSL_DIR="$PROJECT_ROOT/data/nginx/ssl"

if [ $# -lt 3 ]; then
    echo "Usage: $0 <web_domain> <widget_domain> <api_domain> [email] [ws_domain]"
    exit 1
fi

WEB_DOMAIN=$1
WIDGET_DOMAIN=$2
API_DOMAIN=$3
EMAIL=${4:-admin@example.com}
WS_DOMAIN=${5:-}

# Create necessary directories
mkdir -p "$CERTBOT_DIR/conf" "$CERTBOT_DIR/www/.well-known/acme-challenge" "$CERTBOT_DIR/logs"
mkdir -p "$SSL_DIR"

# Build domain list
DOMAINS=("$WEB_DOMAIN" "$WIDGET_DOMAIN" "$API_DOMAIN")
if [ -n "$WS_DOMAIN" ] && [ "$WS_DOMAIN" != "localhost" ]; then
    DOMAINS+=("$WS_DOMAIN")
fi

echo "[INFO] Setting up Let's Encrypt certificates..."
echo "[INFO] Domains: ${DOMAINS[*]}"
echo "[INFO] Email: $EMAIL"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed"
    exit 1
fi

# Check if nginx is running (required for webroot mode)
if ! docker ps --format '{{.Names}}' | grep -q "^tgo-nginx$"; then
    echo "[ERROR] tgo-nginx container is not running"
    echo "[INFO] Please start TGO services first: ./tgo.sh up"
    exit 1
fi

echo "[INFO] Using webroot mode (nginx is running)"
echo ""

# Track success
SUCCESS_COUNT=0
TOTAL_DOMAINS=${#DOMAINS[@]}

# Run certbot for each domain using webroot mode
for domain in "${DOMAINS[@]}"; do
    echo "[INFO] Requesting certificate for: $domain"

    # Use webroot mode - certbot writes challenge files to the webroot
    # nginx serves them via /.well-known/acme-challenge/
    # --force-renewal ensures we renew even if certbot thinks it's not due yet
    docker run --rm \
        -v "$CERTBOT_DIR/conf:/etc/letsencrypt" \
        -v "$CERTBOT_DIR/www:/var/www/certbot" \
        -v "$CERTBOT_DIR/logs:/var/log/letsencrypt" \
        certbot/certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --non-interactive \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        --email "$EMAIL" \
        -d "$domain" || {
        echo "[WARN] Failed to get certificate for $domain"
        echo "[HINT] Make sure the domain points to this server and port 80 is accessible"
        continue
    }

    # Copy certificate to nginx ssl directory
    # Certbot sets 0700 on live/ and archive/ dirs (owned by root inside container),
    # so we copy inside a container to avoid host permission issues.
    mkdir -p "$SSL_DIR/$domain"
    if docker run --rm \
        -v "$CERTBOT_DIR/conf:/etc/letsencrypt:ro" \
        -v "$SSL_DIR/$domain:/output" \
        alpine sh -c "cp -L /etc/letsencrypt/live/$domain/fullchain.pem /output/cert.pem && cp -L /etc/letsencrypt/live/$domain/privkey.pem /output/key.pem && chmod 644 /output/cert.pem /output/key.pem" 2>/dev/null; then
        echo "[INFO] Certificate installed for: $domain"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "[WARN] Failed to copy certificate for $domain"
    fi
done

echo ""
echo "[INFO] SSL setup completed!"
echo "[INFO] Certificates obtained: $SUCCESS_COUNT / $TOTAL_DOMAINS"
echo "[INFO] Certificates stored in: $SSL_DIR"

if [ $SUCCESS_COUNT -gt 0 ]; then
    echo ""
    echo "[INFO] Restarting nginx to apply new certificates..."
    docker restart tgo-nginx >/dev/null 2>&1 && echo "[INFO] Nginx restarted successfully" || echo "[WARN] Could not restart nginx, please run: docker restart tgo-nginx"
fi

if [ $SUCCESS_COUNT -eq 0 ]; then
    echo ""
    echo "[ERROR] No certificates were obtained. Please check:"
    echo "  1. Your domains point to this server's public IP address"
    echo "  2. Port 80 is accessible from the internet (check firewall)"
    echo "  3. DNS has propagated (try: dig $WEB_DOMAIN)"
fi

