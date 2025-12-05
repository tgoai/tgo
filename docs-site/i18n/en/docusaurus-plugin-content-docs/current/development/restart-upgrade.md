---
id: restart-upgrade
title: Restart and Upgrade
sidebar_position: 2
---

# Restart and Upgrade

This page explains how to manage TGO service start/stop and version upgrades.

## Service Management

### Start Services

```bash
./tgo.sh up
```

Source mode:

```bash
./tgo.sh up --source
```

### Stop Services

```bash
./tgo.sh down
```

Stop and remove data volumes (**data will be lost**):

```bash
./tgo.sh down --volumes
```

### Restart Services

```bash
./tgo.sh down
./tgo.sh up
```

### Restart Single Service

```bash
docker compose restart tgo-api
```

## Version Upgrade

### Upgrade to Latest Version

```bash
./tgo.sh upgrade
```

The `upgrade` command automatically:

1. Pulls latest code
2. Updates Docker images
3. Runs database migrations
4. Restarts all services

### Upgrade Command Options

```bash
./tgo.sh upgrade [--source] [--cn]
```

| Option | Description |
|--------|-------------|
| `--source` | Build from source (instead of pre-built images) |
| `--cn` | Use China mirrors for acceleration |

### Install Mode Memory

`upgrade` remembers the mode used during initial installation. For example:

```bash
# Initial install with China mirrors
./tgo.sh install --cn

# Subsequent upgrades auto-use --cn
./tgo.sh upgrade
```

Configuration is saved in `./data/.tgo-install-mode`.

## Uninstall

### Stop and Remove Services

```bash
./tgo.sh uninstall
```

This command will:

1. Stop all containers
2. Remove containers
3. Ask whether to delete data

### Complete Cleanup

For complete cleanup of all data:

```bash
# Stop services
./tgo.sh down --volumes

# Remove data directory
rm -rf ./data

# Remove config files
rm -f .env
rm -rf ./envs
```

## Backup and Restore

### Backup Data

Main data is stored in `./data` directory:

```bash
# Create backup
tar -czvf tgo-backup-$(date +%Y%m%d).tar.gz ./data
```

### Restore Data

```bash
# Stop services
./tgo.sh down

# Restore data
tar -xzvf tgo-backup-20240101.tar.gz

# Start services
./tgo.sh up
```

### Database Backup

Backup PostgreSQL database separately:

```bash
# Export database
docker compose exec postgres pg_dump -U tgo tgo > tgo-db-backup.sql

# Restore database
docker compose exec -T postgres psql -U tgo tgo < tgo-db-backup.sql
```

## Health Check

Check all service status:

```bash
./tgo.sh doctor
```

Example output:

```
=========================================
  TGO Service Health Check
=========================================

  ✅ tgo-api           running (healthy)
  ✅ tgo-ai            running (healthy)
  ✅ tgo-rag           running (healthy)
  ✅ tgo-web           running
  ✅ postgres          running (healthy)
  ✅ redis             running (healthy)
  ✅ nginx             running

-----------------------------------------
Summary: 7/7 services healthy
```
