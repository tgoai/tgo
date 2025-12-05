---
id: debug-tools
title: Debug Tools
sidebar_position: 3
---

# Debug Tools

TGO includes built-in debug tools to help you troubleshoot issues and monitor system status.

## Built-in Debug Tools

TGO provides the following debug tool containers:

| Tool | Purpose | Access URL |
|------|---------|------------|
| **Kafka UI** | Kafka message queue management interface | `http://localhost:8080` |
| **Adminer** | Database management interface | `http://localhost:8081` |

## Start Debug Tools

```bash
./tgo.sh tools start
```

## Stop Debug Tools

```bash
./tgo.sh tools stop
```

## Kafka UI

Kafka UI is a web interface for managing and monitoring Kafka clusters.

### Features

- View topic list
- Browse message content
- Monitor consumer groups
- View cluster status

### Use Cases

- Debug message send/receive issues
- Verify message content
- Monitor consumer lag

### Access

After starting tools, visit: `http://<server-ip>:8080`

## Adminer

Adminer is a lightweight database management tool.

### Features

- Browse database table structure
- Execute SQL queries
- Import/export data
- Edit table data

### Connection Info

| Parameter | Value |
|-----------|-------|
| System | PostgreSQL |
| Server | `postgres` |
| Username | `tgo` (or check `POSTGRES_USER` in `.env`) |
| Password | `tgo` (or check `POSTGRES_PASSWORD` in `.env`) |
| Database | `tgo` (or check `POSTGRES_DB` in `.env`) |

### Access

After starting tools, visit: `http://<server-ip>:8081`

## View Logs

### View All Service Logs

```bash
docker compose logs -f
```

### View Specific Service Logs

```bash
docker compose logs -f tgo-api
docker compose logs -f tgo-ai
docker compose logs -f tgo-rag
```

### View Last N Lines

```bash
docker compose logs --tail=100 tgo-api
```

## Container Debugging

### Enter Container

```bash
docker compose exec tgo-api bash
docker compose exec tgo-ai bash
```

### Check Container Status

```bash
docker compose ps
```

### Check Resource Usage

```bash
docker stats
```

## Health Check

Use the `doctor` command for comprehensive health check:

```bash
./tgo.sh doctor
```

This command checks:

- All service running status
- Database connection
- Nginx configuration
- Data directories
- API endpoint response

## Security Notes

:::warning Note
Debug tools are only for development and debugging environments. In production:

1. Don't expose debug tool ports to the public internet
2. Stop tools when done: `./tgo.sh tools stop`
3. Change default database passwords
:::
