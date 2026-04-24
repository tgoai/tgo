# TGO Dev Environment Redesign

> Date: 2026-04-24
> Status: Approved in chat, written for review
> Scope: Root-level development workflow, Docker Compose layout, Makefile entrypoints, developer onboarding docs

## Summary

TGO's current local development flow is split across multiple modes:

- infrastructure in Docker via `docker-compose.dev.yml`
- production-like services in Docker via `docker-compose.yml`
- source-build overrides in `docker-compose.source.yml`
- service-by-service local startup via root `Makefile`

This makes the "happy path" unclear and forces developers to manually start infra, run migrations, and bring up multiple services in separate terminals. The redesign replaces that with one primary development workflow:

```bash
cp .env.dev.example .env.dev
make dev
```

The new workflow is fully Docker Compose-based, defaults to a full-stack development environment, supports source-mounted hot reload for both backend and frontend services, and still allows developers to disable selected services or profiles when they need a lighter setup.

## Goals

- Make `make dev` the single default way to start local development
- Start a usable full-stack environment with one command
- Run migrations and required bootstrap steps automatically
- Support immediate debugging with source mounts, hot reload, and stable localhost ports
- Keep the environment easy to trim down through Compose profiles or explicit disable flags
- Remove the old split workflow so the team only learns one path

## Non-Goals

- Redesign production deployment
- Change service ownership or runtime architecture
- Optimize for the smallest possible resource footprint by default
- Introduce Kubernetes, Tilt, Skaffold, Dev Containers, or other new orchestration layers

## Options Considered

### Option A: Single large development compose file

Put all development behavior in a brand-new `docker-compose.dev.yml` and stop there.

Pros:
- easy to explain
- straightforward initial implementation

Cons:
- duplicates the shared service topology already present in the repo
- increases drift between development and non-development compose definitions
- encourages another long-lived parallel configuration tree

### Option B: Layered compose base + development override

Keep one shared root compose file for common topology and add one development override for hot reload, mounts, debug behavior, and profiles.

Pros:
- clear separation between stable topology and development-specific behavior
- least duplication
- good fit for "full by default, selectively disabled when needed"
- scales well when new services are added

Cons:
- requires some cleanup of existing compose files and Make targets

### Option C: Rebuild- or watch-driven containers without mounted source

Favor image rebuilds or `docker compose watch` over bind-mounted source trees.

Pros:
- closer to production images
- less variance between local and deployed containers

Cons:
- slower edit-feedback loop for Python and Vite workflows
- worse fit for "make dev then start debugging immediately"

## Recommended Approach

Adopt Option B: a layered Compose design with a shared base and a dedicated development override.

This gives TGO one explicit development path while preserving clean configuration boundaries:

- `docker-compose.yml` becomes the shared service topology base
- `docker-compose.dev.yml` becomes the development override
- `make dev` becomes the only primary local startup command

The older mixed workflow based on `infra-up`, `migrate`, and per-service `dev-*` targets is removed so developers are not choosing between multiple overlapping models.

## Target Developer Experience

### Default path

```bash
cp .env.dev.example .env.dev
make dev
```

Expected result:

- infrastructure starts automatically
- dependencies are waited on before app startup
- migrations and required bootstrap steps run automatically
- all core services come up in development mode
- backend services hot reload on source edits
- frontend services run Vite dev servers inside containers
- developers can open the web and widget UIs on the usual localhost ports

### Common follow-up commands

```bash
make logs
make logs SERVICE=tgo-api
make ps
make restart SERVICE=tgo-ai
make down
make clean
```

### Optional trimming

The default environment is full-stack. Developers can disable selected services or enable optional tooling with profiles or explicit Make variables without learning a second startup model.

Examples:

```bash
make dev DISABLE=flower,adminer
make dev PROFILES=monitoring
make dev DISABLE=rag-worker,workflow-worker
```

Exact syntax may be adjusted during implementation, but the core rule stays the same: default full stack, optional trimming by flag.

## Compose Layout

### `docker-compose.yml`

This file becomes the shared base layer.

Responsibilities:

- define stable service names
- define shared networks and named volumes
- define base environment structure and inter-service URLs
- define health checks and startup dependencies
- define standard container ports
- define persistent data mounts where needed

It should not contain development-only command overrides when those are better expressed in the dev override file.

### `docker-compose.dev.yml`

This file becomes the development override layer.

Responsibilities:

- source bind mounts for active services
- development commands such as `uvicorn --reload`
- frontend Vite dev server commands
- worker commands for background tasks
- debugger-friendly port mappings
- development-only profiles
- local-only helper tooling such as `flower`, `adminer`, or `agentos`

This file also absorbs the useful "source mode" intent currently split into `docker-compose.source.yml`.

### Files to remove or retire

- retire the old infra-only meaning of `docker-compose.dev.yml`
- remove `docker-compose.source.yml` after its useful behavior is folded into the new dev override
- remove old Make targets that start services individually on the host machine
- update docs so they no longer teach the old split workflow

### Expected file changes

The implementation is expected to center on these root-level files:

- modify `docker-compose.yml`
- rewrite `docker-compose.dev.yml` around the new development override model
- remove `docker-compose.source.yml`
- modify `Makefile`
- modify `.env.dev.example`
- add `scripts/dev/init.sh`
- add any small shared wait/helper scripts under `scripts/dev/`
- update `README.md`
- update `README_CN.md`
- update root `AGENTS.md`

## Service Startup Model

### Full-stack by default

`make dev` starts the full development stack by default, including:

- infrastructure: `postgres`, `redis`, `wukongim`
- core backend services: `tgo-api`, `tgo-ai`, `tgo-rag`, `tgo-platform`, `tgo-workflow`, `tgo-plugin-runtime`, `tgo-device-control`
- core frontend services: `tgo-web`, `tgo-widget-js`
- required background workers for normal feature development

This matches the user's stated preference: everything works immediately after `make dev`, with optional ways to turn pieces off later.

### Profiles

Profiles should stay small and meaningful rather than becoming a second configuration language.

Recommended grouping:

- `default/full`: the main development stack
- `monitoring`: optional helpers such as `flower` and `adminer`
- `edge`: optional or less frequently used services that some developers may disable
- `agentos`: keep separate because it is specialized and may require extra credentials or machine capability

Heavy but functionally necessary services should remain in the default stack if removing them breaks normal end-to-end development.

## Environment Strategy

### `.env.dev` as the local-development source of truth

Local development should default to `.env.dev`, not `.env`.

Rationale:

- avoids accidental coupling to production-oriented defaults
- makes the local workflow explicit
- keeps onboarding and docs consistent

### Container networking rules

Inside Compose, services should talk to each other by service name, not `localhost`.

Examples:

- `http://tgo-api:8000`
- `http://tgo-ai:8081`
- `http://tgo-rag:8082`

Only developer-facing ports should be published to the host. This avoids the current mixed model where some settings assume host networking while others assume container networking.

## Initialization and Migrations

### `dev-init` container

Introduce one explicit initialization container or job responsible for startup preparation.

Responsibilities:

- wait for `postgres`, `redis`, and `wukongim` to become healthy
- run all required Alembic migrations in a deterministic order
- run any minimal bootstrap logic required for a usable dev environment
- exit successfully when initialization is complete

Application services should depend on this init step rather than forcing developers to run `make migrate` manually.

### Migration ordering

Migration order should follow actual service dependencies rather than alphabetical order.

Initial recommended order:

1. `tgo-api`
2. `tgo-ai`
3. `tgo-rag`
4. `tgo-platform`
5. `tgo-workflow`
6. `tgo-plugin-runtime`
7. `tgo-device-control`

This order should be validated during implementation against real service startup assumptions.

### Failure behavior

If initialization fails:

- `make dev` should fail clearly
- the failing migration or health check should be visible in logs
- developers should not be left with a silent half-started environment

## Source Mount and Dependency Strategy

### Backend services

Each Python service should use:

- bind-mounted application source for hot reload
- isolated dependency storage inside named Docker volumes rather than host-managed virtualenvs

This avoids:

- host pollution from `.venv` directories
- inconsistent Poetry state across machines
- reinstalling everything from scratch on every container restart

### Frontend services

Each frontend service should use:

- bind-mounted source
- container-managed `node_modules` via named volumes
- Vite dev server bound to `0.0.0.0`

This preserves fast HMR without requiring local `npm install` as the default path.

## Makefile Redesign

The root Makefile should be reduced to a compact set of high-value commands.

Recommended kept commands:

- `make dev`
- `make down`
- `make logs`
- `make ps`
- `make restart SERVICE=<name>`
- `make clean`

Recommended removed commands:

- `make infra-up`
- `make infra-down`
- `make migrate*`
- `make dev-api`
- `make dev-ai`
- `make dev-rag`
- `make dev-platform`
- `make dev-workflow`
- `make dev-plugin`
- `make dev-device`
- `make dev-web`
- `make dev-widget`
- `make dev-backend`
- `make dev-frontend`
- `make dev-all`
- `make stop-all`

The goal is not to preserve every previous escape hatch. The goal is to stop teaching a fragmented workflow.

## Verification Strategy

The redesign should be validated from a fresh developer workflow, not just by checking Compose syntax.

Required validation outcomes:

- `cp .env.dev.example .env.dev && make dev` succeeds on a clean local checkout
- `docker compose ps` shows the expected full development stack as healthy or running
- migrations complete through the init flow without a separate manual command
- `tgo-web` is reachable on `http://localhost:5173`
- `tgo-widget-js` is reachable on `http://localhost:5174`
- `tgo-api` and `tgo-ai` health endpoints respond on their published localhost ports
- changing a backend source file triggers reload in the relevant container
- changing a frontend source file triggers HMR in the relevant Vite container
- `make logs SERVICE=tgo-api` and `make restart SERVICE=tgo-ai` work as the main operational escape hatches

This verification should be part of the implementation plan so the new workflow is proven end-to-end before the old one is removed.

## Documentation Changes

These locations should be updated to reflect the new default workflow:

- `README.md`
- `README_CN.md`
- root `AGENTS.md`
- any service-level onboarding docs that currently point developers to the removed root flow

The new quick-start for development should be concise and consistent:

```bash
cp .env.dev.example .env.dev
make dev
```

Advanced options such as `PROFILES` or `DISABLE` should be documented as secondary usage, not the main path.

## Risks and Mitigations

### Risk: resource usage is higher with full-stack-by-default

Mitigation:
- keep the default full stack because it satisfies the product goal
- provide explicit opt-out flags for workers or optional tooling
- document the most useful trimming combinations

### Risk: dependency installation inside containers becomes slow on first boot

Mitigation:
- use named volumes for dependency caches
- structure Dockerfiles and compose commands for reuse
- keep first-run cost acceptable in exchange for a much simpler steady-state workflow

### Risk: migration job ordering or readiness assumptions are wrong

Mitigation:
- make init logs explicit
- validate order during implementation
- keep the init script centralized rather than spreading shell logic across many services

### Risk: old docs and scripts keep developers on the previous workflow

Mitigation:
- remove or sharply deprecate old targets
- update root docs in the same change set
- treat the old workflow as removed, not just "also available"

## Rollout Plan

Implementation should happen in one coordinated change set that:

1. introduces the new layered dev compose model
2. adds the init script and Makefile entrypoints
3. updates documentation to point to `make dev`
4. removes old root-level development commands and compose files that are no longer needed

The repository should not keep both workflows active long-term, because that recreates the same ambiguity this redesign is meant to remove.

## Acceptance Criteria

The redesign is successful when:

- a developer can clone the repo, create `.env.dev`, run `make dev`, and reach a working local environment without manual per-service startup
- backend edits reload without rebuilding the full environment
- frontend edits reload through containerized Vite dev servers
- migrations run automatically on startup through a single init flow
- docs teach one primary development workflow
- the old step-by-step host-based dev flow is removed from the root workflow

## Open Implementation Questions

- which services should count as default-required workers versus optional-heavy workers
- whether any bootstrap step beyond migrations is required for a useful first-run environment
- the exact Make variable shape for selective disable behavior (`DISABLE`, `SERVICES`, or profile-only)
- whether some specialized services should remain available only behind explicit profiles

These are implementation details, not design blockers. They should be finalized in the implementation plan while preserving the approved product direction.
