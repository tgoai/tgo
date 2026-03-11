---
name: local-services
description: Start, stop, and check local development services with intelligent minimum-set management. Trigger when services need to be running for functional verification or manual testing — starts the minimum required set (infrastructure + tgo-api + tgo-ai) by default, with optional extras auto-detected from git diff or specified manually. Includes status checking and graceful shutdown.
---

# local-services

## Purpose
Start, stop, and check local development services. Knows the minimum required set and can auto-detect additional services needed based on code changes.

## Trigger
- Before running functional verification (services must be running)
- When starting a development session
- When agent needs to test API changes at runtime

## Minimum Services
The core platform requires only 3 things to be functional:
1. **Infrastructure** — PostgreSQL, Redis, WuKongIM (`make infra-up`)
2. **tgo-api** — Core API gateway (port 8000)
3. **tgo-ai** — LLM / Agent runtime (port 8081)

All other services are optional and can be added based on what you're working on.

## Service Map

| Service | Make target | Port | When needed |
|---------|------------|------|-------------|
| Infrastructure | `make infra-up` | 5432/6379/5001 | Always |
| tgo-api | `make dev-api` | 8000 | Always |
| tgo-ai | `make dev-ai` | 8081 | Always |
| tgo-rag | `make dev-rag` | 18082 | Knowledge base / RAG changes |
| tgo-platform | `make dev-platform` | 8003 | Channel integration changes |
| tgo-workflow | `make dev-workflow` | 8004 | Workflow engine changes |
| tgo-plugin-runtime | `make dev-plugin` | 8090 | Plugin / MCP tool changes |
| tgo-device-control | `make dev-device` | 8085 | Device management changes |
| tgo-web | `make dev-web` | 5173 | Admin frontend changes |
| tgo-widget-js | `make dev-widget` | 5174 | Visitor widget changes |
| RAG worker | `make dev-rag-worker` | — | Document processing tasks |
| Workflow worker | `make dev-wf-worker` | — | Workflow execution tasks |

## Usage
```bash
# Start minimum services (infra + api + ai)
bash .skills/local-services/scripts/start.sh

# Start minimum + specific extras
bash .skills/local-services/scripts/start.sh rag web

# Start minimum + auto-detect extras from git diff
bash .skills/local-services/scripts/start.sh --auto

# Start everything
bash .skills/local-services/scripts/start.sh --all

# Check what's running
bash .skills/local-services/scripts/status.sh

# Stop all services
bash .skills/local-services/scripts/stop.sh
```
