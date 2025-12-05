---
id: env-vars
title: Environment Variables
sidebar_position: 1
---

# Environment Variables

TGO uses environment variables to configure various services. This page introduces the main configuration files and commonly used environment variables.

## Configuration File Structure

TGO configuration is divided into two layers:

```
tgo/
├── .env                    # Global configuration (ports, host, etc.)
└── envs/                   # Individual service configurations
    ├── tgo-api.env
    ├── tgo-ai.env
    ├── tgo-rag.env
    ├── tgo-platform.env
    ├── tgo-web.env
    ├── tgo-widget-app.env
    └── wukongim.env
```

## Global Configuration (.env)

The `.env` file in the root directory contains global configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVER_HOST` | Server address (IP or domain) | Auto-detected |
| `VITE_API_BASE_URL` | Frontend API address | `http://localhost` |
| `NGINX_PORT` | HTTP port | `80` |
| `NGINX_SSL_PORT` | HTTPS port | `443` |
| `POSTGRES_DB` | Database name | `tgo` |
| `POSTGRES_USER` | Database user | `tgo` |
| `POSTGRES_PASSWORD` | Database password | `tgo` |

### Modifying Global Configuration

Edit the `.env` file directly:

```bash
vi .env
```

Restart services after modification:

```bash
./tgo.sh down
./tgo.sh up
```

## Service Configuration (envs/)

### tgo-api.env

API service configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT secret (auto-generated) | - |
| `PORT` | Service port | `8000` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `API_BASE_URL` | Public API URL | `http://localhost:8000` |
| `MAX_FILE_SIZE` | Max file upload size | `10485760` (10MB) |

### tgo-ai.env

AI service configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | `8081` |
| `LOG_LEVEL` | Log level | `DEBUG` |
| `API_SERVICE_URL` | API service URL | `http://tgo-api:8001` |
| `RAG_SERVICE_URL` | RAG service URL | `http://tgo-rag:8082` |
| `MCP_SERVICE_URL` | MCP service URL | `http://tgo-mcp-v4:8084` |

## Configuration Best Practices

### 1. Don't Modify Template Directories

`envs.docker/` and `envs.example/` are template directories. During installation, they are automatically copied to `envs/`. Only modify files in `envs/`.

### 2. SECRET_KEY Security

`SECRET_KEY` is auto-generated during first installation. If setting manually, ensure:
- At least 32 characters
- Use random string
- Don't use default values

Generate a new key:

```bash
openssl rand -hex 32
```

### 3. Production Configuration

For production, we recommend modifying:

```bash
# .env
POSTGRES_PASSWORD=<strong-password>

# envs/tgo-api.env
SECRET_KEY=<random-key>
LOG_LEVEL=INFO
```

### 4. Restart After Changes

Restart services after any configuration changes:

```bash
# Restart all services
./tgo.sh down
./tgo.sh up

# Or restart specific service
docker compose restart tgo-api
```
