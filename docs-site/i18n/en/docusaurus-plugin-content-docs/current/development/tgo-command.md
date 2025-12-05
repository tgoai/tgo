---
id: tgo-command
title: TGO Commands
sidebar_position: 4
---

# TGO Commands

`tgo.sh` is the main management script for TGO, providing all common commands for deployment, operations, and configuration.

## Command Overview

```bash
./tgo.sh <command> [options]
```

## Basic Commands

### help

Display help information:

```bash
./tgo.sh help
```

### install

First-time installation and start all services:

```bash
./tgo.sh install [--source] [--cn]
```

| Option | Description |
|--------|-------------|
| `--source` | Build from source (instead of pre-built images) |
| `--cn` | Use China mirrors for acceleration |

Examples:

```bash
# Default install (using pre-built images)
./tgo.sh install

# Source install
./tgo.sh install --source

# Install with China mirrors
./tgo.sh install --cn

# Combined options
./tgo.sh install --source --cn
```

### up

Start all services (without initialization):

```bash
./tgo.sh up [--source] [--cn]
```

Use after `down` to restart services.

### down

Stop and remove all containers:

```bash
./tgo.sh down [--volumes]
```

| Option | Description |
|--------|-------------|
| `--volumes` | Also remove data volumes (**data will be lost**) |

### upgrade

Upgrade to latest version:

```bash
./tgo.sh upgrade [--source] [--cn]
```

Automatically remembers the mode used during initial installation.

### doctor

Check health status of all services:

```bash
./tgo.sh doctor
```

Output includes:

- Service running status
- Configuration checks
- Endpoint response tests

## Service Management Commands

### service

Manage core services:

```bash
./tgo.sh service <start|stop|remove> [--source] [--cn]
```

| Subcommand | Description |
|------------|-------------|
| `start` | Start services |
| `stop` | Stop services |
| `remove` | Remove services |

### tools

Manage debug tools (Kafka UI, Adminer):

```bash
./tgo.sh tools <start|stop>
```

| Subcommand | Description |
|------------|-------------|
| `start` | Start debug tools |
| `stop` | Stop debug tools |

### build

Build specific service from source:

```bash
./tgo.sh build <service>
```

| Service | Description |
|---------|-------------|
| `api` | Build tgo-api |
| `ai` | Build tgo-ai |
| `rag` | Build tgo-rag |
| `platform` | Build tgo-platform |
| `web` | Build tgo-web |
| `widget` | Build tgo-widget |
| `all` | Build all services |

## Configuration Commands

### config

Domain and SSL certificate configuration:

```bash
./tgo.sh config <subcommand> [args]
```

#### Domain Configuration

```bash
./tgo.sh config web_domain <domain>      # Set Web domain
./tgo.sh config widget_domain <domain>   # Set Widget domain
./tgo.sh config api_domain <domain>      # Set API domain
./tgo.sh config ws_domain <domain>       # Set WebSocket domain
```

#### SSL Configuration

```bash
./tgo.sh config ssl_mode <auto|manual|none>   # Set SSL mode
./tgo.sh config ssl_email <email>              # Set Let's Encrypt email
./tgo.sh config ssl_manual <cert> <key> [domain]  # Install manual certificate
./tgo.sh config setup_letsencrypt              # Request Let's Encrypt certificates
```

#### Other Config Commands

```bash
./tgo.sh config apply   # Apply config (regenerate Nginx config)
./tgo.sh config show    # Show current configuration
```

## Environment Variables

The one-click installation script supports these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `REF` | Deploy version (branch/tag/commit) | `latest` |
| `DIR` | Installation directory | `./tgo` |

Example:

```bash
REF=v1.0.0 DIR=/opt/tgo curl -fsSL https://raw.githubusercontent.com/tgoai/tgo/main/bootstrap.sh | bash
```

## Configuration Files

| File | Description |
|------|-------------|
| `.env` | Global environment variables |
| `envs/*.env` | Service environment variables |
| `data/.tgo-install-mode` | Install mode memory |
| `data/.tgo-domain-config` | Domain and SSL config |

## Data Directories

| Directory | Description |
|-----------|-------------|
| `data/postgres/` | PostgreSQL data |
| `data/redis/` | Redis data |
| `data/wukongim/` | WuKongIM data |
| `data/nginx/` | Nginx config and certificates |
| `data/uploads/` | Uploaded files |

## Usage Recommendations

1. **Production**: Use `./tgo.sh install` with default image deployment
2. **Development**: Use `./tgo.sh install --source` for source deployment
3. **China servers**: Add `--cn` for acceleration
4. **Troubleshooting**: Run `./tgo.sh doctor` first to check status
