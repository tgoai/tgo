#!/bin/bash
# Setup SSL certificates for Let's Encrypt
# Usage: ./scripts/setup-ssl.sh <domain1> <domain2> <domain3> [email]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/data/.tgo-domain-config"
CERTBOT_DIR="$PROJECT_ROOT/data/certbot"
SSL_DIR="$PROJECT_ROOT/data/nginx/ssl"

if [ $# -lt 3 ]; then
    echo "Usage: $0 <web_domain> <widget_domain> <api_domain> [email]"
    exit 1
fi

WEB_DOMAIN=$1
WIDGET_DOMAIN=$2
API_DOMAIN=$3
EMAIL=${4:-admin@example.com}

# Create necessary directories
mkdir -p "$CERTBOT_DIR/conf" "$CERTBOT_DIR/www/.well-known/acme-challenge" "$CERTBOT_DIR/logs"
mkdir -p "$SSL_DIR"

echo "[INFO] Setting up Let's Encrypt certificates..."
echo "[INFO] Domains: $WEB_DOMAIN, $WIDGET_DOMAIN, $API_DOMAIN"
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
TOTAL_DOMAINS=3

# Run certbot for each domain using webroot mode
for domain in "$WEB_DOMAIN" "$WIDGET_DOMAIN" "$API_DOMAIN"; do
    echo "[INFO] Requesting certificate for: $domain"

    # Use webroot mode - certbot writes challenge files to the webroot
    # nginx serves them via /.well-known/acme-challenge/
    docker run --rm \
        -v "$CERTBOT_DIR/conf:/etc/letsencrypt" \
        -v "$CERTBOT_DIR/www:/var/www/certbot" \
        -v "$CERTBOT_DIR/logs:/var/log/letsencrypt" \
        certbot/certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --agree-tos \
        --no-eff-email \
        --email "$EMAIL" \
        -d "$domain" || {
        echo "[WARN] Failed to get certificate for $domain"
        echo "[HINT] Make sure the domain points to this server and port 80 is accessible"
        continue
    }

    # Copy certificate to nginx ssl directory
    mkdir -p "$SSL_DIR/$domain"
    if [ -f "$CERTBOT_DIR/conf/live/$domain/fullchain.pem" ]; then
        cp "$CERTBOT_DIR/conf/live/$domain/fullchain.pem" "$SSL_DIR/$domain/cert.pem"
        cp "$CERTBOT_DIR/conf/live/$domain/privkey.pem" "$SSL_DIR/$domain/key.pem"
        echo "[INFO] Certificate installed for: $domain"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    fi
done

echo ""
echo "[INFO] SSL setup completed!"
echo "[INFO] Certificates obtained: $SUCCESS_COUNT / $TOTAL_DOMAINS"
echo "[INFO] Certificates stored in: $SSL_DIR"

if [ $SUCCESS_COUNT -gt 0 ]; then
    echo ""
    echo "[INFO] Reloading nginx to apply new certificates..."
    docker exec tgo-nginx nginx -s reload 2>/dev/null || echo "[WARN] Could not reload nginx"
fi

if [ $SUCCESS_COUNT -eq 0 ]; then
    echo ""
    echo "[ERROR] No certificates were obtained. Please check:"
    echo "  1. Your domains point to this server's public IP address"
    echo "  2. Port 80 is accessible from the internet (check firewall)"
    echo "  3. DNS has propagated (try: dig $WEB_DOMAIN)"
fi

