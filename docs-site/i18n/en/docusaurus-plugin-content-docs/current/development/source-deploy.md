---
id: source-deploy
title: Source Deployment
sidebar_position: 1
---

# Source Deployment

This page explains how to build and deploy TGO from source code, suitable for customization or development debugging.

## Difference from Image Deployment

| Method | Description | Use Case |
|--------|-------------|----------|
| **Image Deployment** (default) | Uses pre-built Docker images | Production, quick deployment |
| **Source Deployment** | Builds images from local source | Development, customization |

## Source Deployment Steps

### 1. Clone Repository

```bash
git clone https://github.com/tgoai/tgo.git
cd tgo
```

For users in China:

```bash
git clone https://gitee.com/tgoai/tgo.git
cd tgo
```

### 2. Initialize Submodules

TGO service source code is managed as Git submodules in the `repos/` directory:

```bash
git submodule update --init --recursive
```

### 3. Run Source Installation

Use the `--source` parameter for source deployment:

```bash
./tgo.sh install --source
```

For users in China, add `--cn` for mirrors:

```bash
./tgo.sh install --source --cn
```

## Source Directory Structure

```
tgo/
└── repos/
    ├── tgo-api/        # Backend API service
    ├── tgo-ai/         # AI inference service
    ├── tgo-rag/        # RAG service
    ├── tgo-platform/   # Platform management service
    ├── tgo-web/        # Web console
    └── tgo-widget/     # Widget component
```

## Build Specific Services

If you only modified one service, rebuild it individually:

```bash
# Build specific service
./tgo.sh build api      # Build tgo-api
./tgo.sh build ai       # Build tgo-ai
./tgo.sh build rag      # Build tgo-rag
./tgo.sh build platform # Build tgo-platform
./tgo.sh build web      # Build tgo-web
./tgo.sh build widget   # Build tgo-widget

# Build all services
./tgo.sh build all
```

Restart services after building:

```bash
./tgo.sh down
./tgo.sh up --source
```

## Development Workflow

### Modify Code

1. Enter the service directory:
   ```bash
   cd repos/tgo-api
   ```

2. Make your changes

3. Rebuild and restart:
   ```bash
   cd ../..
   ./tgo.sh build api
   ./tgo.sh down
   ./tgo.sh up --source
   ```

### View Logs

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f tgo-api
```

### Enter Container for Debugging

```bash
docker compose exec tgo-api bash
```

## Notes

1. **First build takes longer**: Source build requires downloading dependencies and compiling, may take 10-30 minutes initially

2. **Disk Space**: Source deployment requires more disk space for source code and build cache

3. **Network Requirements**: Build process needs to download dependency packages, ensure network connectivity

4. **Branch Sync**: If main repo is updated, remember to sync submodules:
   ```bash
   git pull
   git submodule update --recursive
   ```
