---
id: domain-ssl
title: Domain and SSL
sidebar_position: 2
---

# Domain and SSL Configuration

This page explains how to configure domains for Web / Widget / API services and enable HTTPS certificates.

## Configure Domains

TGO supports separate domains for different services:

| Service | Config Key | Example |
|---------|------------|---------|
| Web Console | `web_domain` | `www.example.com` |
| Widget Component | `widget_domain` | `widget.example.com` |
| API Service | `api_domain` | `api.example.com` |
| WebSocket | `ws_domain` | `ws.example.com` |

### Set Domains

Run in the repository root directory:

```bash
./tgo.sh config web_domain www.example.com
./tgo.sh config widget_domain widget.example.com
./tgo.sh config api_domain api.example.com
./tgo.sh config ws_domain ws.example.com
```

### Apply Configuration

After setting domains, run `apply` to activate:

```bash
./tgo.sh config apply
```

This automatically generates/updates Nginx configuration to proxy different domains to their respective services.

### View Current Configuration

```bash
./tgo.sh config show
```

## Enable HTTPS

TGO supports two SSL certificate configuration methods:

### Option A: Let's Encrypt Auto Certificate (Recommended)

**Prerequisites**:

- All domain DNS records point to your server's public IP
- Server ports 80/443 are accessible from the internet
- Server can access Let's Encrypt services

**Configuration Steps**:

```bash
# 1. Set certificate email (for expiration notices)
./tgo.sh config ssl_email your-email@example.com

# 2. Request certificates
./tgo.sh config setup_letsencrypt

# 3. Apply configuration
./tgo.sh config apply
```

**Auto Renewal**:

Let's Encrypt certificates are valid for 90 days. Set up a cron job for auto-renewal:

```bash
# Edit crontab
crontab -e

# Add this line (check renewal daily at 2 AM)
0 2 * * * cd /path/to/tgo && ./tgo.sh config setup_letsencrypt >/dev/null 2>&1
```

### Option B: Use Existing Certificates

If you already have certificates from another CA:

```bash
# Install same certificate for all domains (wildcard certificate)
./tgo.sh config ssl_manual /path/to/cert.pem /path/to/key.pem

# Or install certificate for specific domain
./tgo.sh config ssl_manual /path/to/cert.pem /path/to/key.pem www.example.com

# Apply configuration
./tgo.sh config apply
```

### Disable SSL

For HTTP-only access:

```bash
./tgo.sh config ssl_mode none
./tgo.sh config apply
```

## Complete Configuration Example

Here's a complete domain and SSL configuration workflow:

```bash
# 1. Configure domains
./tgo.sh config web_domain www.example.com
./tgo.sh config widget_domain widget.example.com
./tgo.sh config api_domain api.example.com

# 2. Configure Let's Encrypt
./tgo.sh config ssl_email admin@example.com
./tgo.sh config setup_letsencrypt

# 3. Apply all configurations
./tgo.sh config apply

# 4. View results
./tgo.sh config show
```

After configuration, access via HTTPS:

- `https://www.example.com` - Web Console
- `https://widget.example.com` - Widget Component
- `https://api.example.com` - API Service
