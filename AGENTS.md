# TGO Workspace — AGENTS.md

> 最近校准: 2026-03-11

## Policies & Mandatory Skills

### `$local-services`

Before any runtime verification or manual testing, ensure local services are running. Use `$local-services` to start the minimum set (infrastructure + tgo-api + tgo-ai) or check current status.

Run it when:
- You need to run `$functional-verification` but services are not up
- Starting a new development session that involves backend changes

Skip when:
- Only making docs, config, or frontend-only changes that don't need a running server
- Services are already confirmed running via `$local-services` status check

### `$implementation-strategy`

Before modifying runtime, API, or cross-service code, use `$implementation-strategy` to analyze change impact — it maps files to service ownership, outputs the dependency graph, and lists sync points.

Run it when:
- Changes touch `repos/*/app/api/`, `repos/*/app/services/`, `repos/*/app/runtime/`, or `repos/*/app/schemas/`
- Changes span 2+ services
- You're unsure which upstream/downstream services are affected

Skip when:
- Single-service, single-file changes with obvious scope (e.g., fixing a typo in one component)

### `$code-change-verification`

Run `$code-change-verification` before marking work complete when changes affect runtime code, build, or tests. This runs lint, type-check, and build per service.

Run it when:
- Changes touch any code in `repos/*/`

Skip when:
- Changes are docs-only (`AGENTS.md`, `README.md`, `.skills/`)
- Changes are config-only (`.env*`, `docker-compose*`, `Makefile`) with no code impact

### `$db-migration-check`

Use `$db-migration-check` to verify that model changes have corresponding Alembic migrations.

Run it when:
- Changes touch `models/*.py` or `models/**/*.py` in any service

Skip when:
- No model files were modified

### `$cross-service-sync`

Use `$cross-service-sync` to detect schema/type changes that may need synchronized updates in other services.

Run it when:
- Changes touch files under `schemas/`, `types/`, or API response structures
- Changes modify Pydantic models that are consumed by other services

Skip when:
- Schema changes are internal to a single service with no external consumers

### `$streaming-protocol-check`

Use `$streaming-protocol-check` to verify streaming protocol consistency across producer (tgo-ai), relay (tgo-api), and consumers (tgo-web, tgo-widget-js, tgo-widget-miniprogram).

Run it when:
- Changes touch `streaming/`, `wukongim`, SSE, `stream.delta`, `MixedStreamParser`, or `json-render` code

Skip when:
- Changes don't involve any streaming or real-time messaging paths

### `$functional-verification`

Use `$functional-verification` alongside `$code-change-verification` to validate API changes at runtime using tgo-cli (staff) and tgo-widget-cli (visitor). This goes beyond static checks — it makes real API calls.

Run it when:
- Changes affect backend API endpoints, service logic, chat flow, agent config, knowledge/RAG, workflow, or platform integration
- Local services are running (use `$local-services` first if not)

Skip when:
- Changes are frontend-only or static-check is sufficient
- Local services are not available and cannot be started

### `$pr-draft-summary`

Use `$pr-draft-summary` when reporting code changes as complete — it generates a change summary grouped by service with commit history and diff stats.

Run it when:
- Work is finished and ready to commit or create a pull request

Skip when:
- Trivial or conversation-only tasks where no PR summary is expected

## Development Workflow

1. Read the target service's `AGENTS.md` before making changes.
2. If changes span multiple services or touch APIs, run `$implementation-strategy` to understand impact.
3. If local services are needed, run `$local-services` to start the minimum set.
4. Make changes — follow the target service's Rules and Constraints.
5. If model files changed, run `$db-migration-check`.
6. If schema/type files changed, run `$cross-service-sync`.
7. If streaming code changed, run `$streaming-protocol-check`.
8. Run `$code-change-verification` to validate lint/type-check/build.
9. If backend logic changed and services are running, run `$functional-verification` alongside `$code-change-verification`.
10. When work is complete, run `$pr-draft-summary` to generate the PR summary.

## Architecture

```mermaid
graph TB
    WEB[tgo-web] --> API[tgo-api]
    WIDGET[tgo-widget-js] --> API
    MINI[tgo-widget-miniprogram] --> API
    API --> AI[tgo-ai]
    API --> RAG[tgo-rag]
    API --> PLATFORM[tgo-platform]
    API --> WORKFLOW[tgo-workflow]
    API --> PLUGIN[tgo-plugin-runtime]
    API --> DEVICE[tgo-device-control]
    AI --> PLUGIN
    AGENT[tgo-device-agent] --> DEVICE
    API --> IM[WuKongIM]
```

## Services

| Service | Dir | Role | Port |
|:--------|:----|:-----|:-----|
| tgo-api | `repos/tgo-api` | Core API gateway, multi-tenant | 8000 |
| tgo-ai | `repos/tgo-ai` | LLM, Agent runtime | 8081 |
| tgo-rag | `repos/tgo-rag` | Knowledge base, RAG | 18082 |
| tgo-platform | `repos/tgo-platform` | Channel message sync | 8003 |
| tgo-workflow | `repos/tgo-workflow` | Workflow engine | 8004 |
| tgo-plugin-runtime | `repos/tgo-plugin-runtime` | Plugin & MCP runtime | 8090 |
| tgo-device-control | `repos/tgo-device-control` | Device management | 8085 |
| tgo-device-agent | `repos/tgo-device-agent` | Device-side Go agent | N/A |
| tgo-web | `repos/tgo-web` | Admin frontend | 5173 |
| tgo-widget-js | `repos/tgo-widget-js` | Visitor chat widget | 5174 |
| tgo-widget-miniprogram | `repos/tgo-widget-miniprogram` | WeChat mini-program widget | N/A |
| tgo-cli | `repos/tgo-cli` | Staff CLI + MCP server | N/A |
| tgo-widget-cli | `repos/tgo-widget-cli` | Visitor CLI + MCP server | N/A |

Infra: PostgreSQL + pgvector, Redis, WuKongIM, Celery (RAG/Workflow workers)

## Constraints

- No bare `dict` (Python) or `any` (TypeScript) in business interfaces
- No cross-service direct DB access — use HTTP clients in `services/`
- No hardcoded URLs, secrets, or environment addresses — use `.env` + config
- Model/table changes must include Alembic migration
- Migration and code must be committed together

## Tech Stack

- Backend: Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
- Frontend: tgo-web (React 19 + TS + Vite 7 + Zustand), tgo-widget-js (React 18 + TS + Vite 5)
- Device: Go 1.22 (tgo-device-agent)
- Mini-program: Pure JS (ES5), WeChat native components

## Quick Start

```bash
cp .env.dev.example .env.dev && make install
make infra-up && make migrate
make dev-api    # or: make dev-all
```

## Service AGENTS.md Entry Points

- [`repos/tgo-ai/AGENTS.md`](repos/tgo-ai/AGENTS.md)
- [`repos/tgo-api/AGENTS.md`](repos/tgo-api/AGENTS.md)
- [`repos/tgo-web/AGENTS.md`](repos/tgo-web/AGENTS.md)
- [`repos/tgo-rag/AGENTS.md`](repos/tgo-rag/AGENTS.md)
- [`repos/tgo-platform/AGENTS.md`](repos/tgo-platform/AGENTS.md)
- [`repos/tgo-workflow/AGENTS.md`](repos/tgo-workflow/AGENTS.md)
- [`repos/tgo-plugin-runtime/AGENTS.md`](repos/tgo-plugin-runtime/AGENTS.md)
- [`repos/tgo-device-control/AGENTS.md`](repos/tgo-device-control/AGENTS.md)
- [`repos/tgo-device-agent/AGENTS.md`](repos/tgo-device-agent/AGENTS.md)
- [`repos/tgo-widget-js/AGENTS.md`](repos/tgo-widget-js/AGENTS.md)
- [`repos/tgo-widget-miniprogram/AGENTS.md`](repos/tgo-widget-miniprogram/AGENTS.md)
- [`repos/tgo-cli/AGENTS.md`](repos/tgo-cli/AGENTS.md)
- [`repos/tgo-widget-cli/AGENTS.md`](repos/tgo-widget-cli/AGENTS.md)
