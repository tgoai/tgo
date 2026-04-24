# TGO Dev Environment Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current multi-step host/Docker mixed development workflow with a single `make dev` entrypoint that builds the local images, starts infra, runs migrations automatically, and launches the full stack in hot-reload mode.

**Architecture:** Keep `docker-compose.yml` as the shared base topology and convert `docker-compose.dev.yml` into a true development override. Build Python images locally from existing service Dockerfiles, bind-mount service source into `/app`, and preserve dependencies with named volumes mounted at `/app/.venv`; run frontend dev servers in Node containers with bind mounts plus `node_modules` volumes. Use a tiny root-level init script to wait for infra and run migration one-shots in a deterministic order before the full stack starts.

**Tech Stack:** Docker Compose v2, GNU Make, Bash, existing Python service Dockerfiles, Node 20 Alpine dev containers, Poetry-managed Python environments, Vite dev servers

---

### Task 1: Collapse source mode into the shared Compose base

**Files:**
- Modify: `docker-compose.yml`
- Delete: `docker-compose.source.yml`
- Test: `docker compose --env-file .env.dev -f docker-compose.yml config`

- [ ] **Step 1: Capture the current local-build baseline**

Run:

```bash
if [ ! -f .env.dev ]; then cp .env.dev.example .env.dev; fi
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.source.yml config > /tmp/tgo-dev.before.yml
```

Expected: command succeeds and `/tmp/tgo-dev.before.yml` contains `build:` sections for the source-mode services.

- [ ] **Step 2: Merge every local build context from `docker-compose.source.yml` into `docker-compose.yml`**

Update these services in `docker-compose.yml` so they all keep both `image:` and `build:`:

- `tgo-rag-worker`
- `tgo-rag-beat`
- `tgo-rag`
- `tgo-ai`
- `tgo-api`
- `tgo-plugin-runtime`
- `tgo-device-control`
- `tgo-platform`
- `tgo-workflow`
- `tgo-workflow-worker`

Also add the named volumes the dev override will need later:

```yaml
volumes:
  plugin-socket:
  tgo-api-venv:
  tgo-ai-venv:
  tgo-rag-venv:
  tgo-platform-venv:
  tgo-workflow-venv:
  tgo-plugin-runtime-venv:
  tgo-device-control-venv:
  tgo-web-node-modules:
  tgo-widget-node-modules:
```

- [ ] **Step 3: Remove the obsolete source overlay file**

Delete:

```text
docker-compose.source.yml
```

- [ ] **Step 4: Validate the shared base on its own**

Run:

```bash
docker compose --env-file .env.dev -f docker-compose.yml config > /tmp/tgo-base.after.yml
```

Expected: command succeeds without referencing the deleted file, and the base file still defines all core services.

- [ ] **Step 5: Commit the topology collapse**

Run:

```bash
git add docker-compose.yml docker-compose.source.yml
git commit -m "refactor: fold source compose into shared base"
```

### Task 2: Rewrite the dev override for backend hot reload and migration one-shots

**Files:**
- Modify: `docker-compose.dev.yml`
- Modify: `.env.dev.example`
- Create: `scripts/dev/wait-for.sh`
- Create: `scripts/dev/init.sh`
- Test: `docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config`

- [ ] **Step 1: Confirm the current override is still infra-only**

Run:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config | rg "migrate-api|/app/.venv|uvicorn.*--reload" -n
```

Expected: no matches, proving the backend dev contract is not implemented yet.

- [ ] **Step 2: Rewrite `.env.dev.example` for container-first development**

Replace the current host-local defaults with Compose-network defaults for service-to-service traffic:

```dotenv
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379
API_SERVICE_URL=http://tgo-api:8000
AI_SERVICE_URL=http://tgo-ai:8081
RAG_SERVICE_URL=http://tgo-rag:8082
PLATFORM_SERVICE_URL=http://tgo-platform:8003
WORKFLOW_SERVICE_URL=http://tgo-workflow:8000
PLUGIN_RUNTIME_URL=http://tgo-plugin-runtime:8090
DEVICE_CONTROL_SERVICE_URL=http://tgo-device-control:8085
```

Keep host-facing ports as explicit published-port variables:

```dotenv
TGO_API_PORT=8000
TGO_AI_PORT=8081
TGO_RAG_PORT=8082
TGO_PLATFORM_PORT=8003
TGO_WORKFLOW_PORT=8004
TGO_PLUGIN_RUNTIME_PORT=8090
TGO_DEVICE_CONTROL_PORT=8085
TGO_WEB_PORT=5173
TGO_WIDGET_PORT=5174
```

- [ ] **Step 3: Turn `docker-compose.dev.yml` into a real backend dev override**

Rewrite `docker-compose.dev.yml` so each Python service:

- uses `env_file: [.env.dev]`
- bind-mounts its repo into `/app`
- mounts its named venv volume into `/app/.venv`
- publishes its localhost debug port
- runs its reload-friendly command

Use this pattern for each backend service:

```yaml
tgo-api:
  env_file:
    - .env.dev
  volumes:
    - ./repos/tgo-api:/app
    - tgo-api-venv:/app/.venv
    - ./data/tgo-api/uploads:/app/uploads
  ports:
    - "${TGO_API_PORT:-8000}:8000"
  command:
    - /app/.venv/bin/uvicorn
    - app.main:app
    - --host
    - 0.0.0.0
    - --port
    - "8000"
    - --reload
```

Apply equivalent overrides to:

- `tgo-ai`
- `tgo-rag`
- `tgo-platform`
- `tgo-workflow`
- `tgo-plugin-runtime`
- `tgo-device-control`
- `tgo-rag-worker`
- `tgo-rag-beat`
- `tgo-workflow-worker`

Add one-shot migration services alongside them:

- `migrate-api`
- `migrate-ai`
- `migrate-rag`
- `migrate-platform`
- `migrate-workflow`
- `migrate-plugin`
- `migrate-device`

Each migration service should reuse the same mounts and environment as its runtime service and run only the Alembic command, for example:

```yaml
migrate-api:
  env_file:
    - .env.dev
  volumes:
    - ./repos/tgo-api:/app
    - tgo-api-venv:/app/.venv
  command:
    - /app/.venv/bin/alembic
    - upgrade
    - head
```

- [ ] **Step 4: Add the init/wait helper scripts**

Create `scripts/dev/wait-for.sh` as a generic host-side readiness helper with `tcp` and `http` modes.

Create `scripts/dev/init.sh` so it:

- waits for Postgres on `localhost:${POSTGRES_PORT:-5432}`
- waits for Redis on `localhost:${REDIS_PORT:-6379}`
- waits for WuKongIM on `http://localhost:5001/health`
- runs the migration services in this order:

```text
migrate-api
migrate-ai
migrate-rag
migrate-platform
migrate-workflow
migrate-plugin
migrate-device
```

Support a dry-run mode:

```bash
./scripts/dev/init.sh --dry-run
```

Expected dry-run output: the infra wait checks and the seven migration service names, in order.

- [ ] **Step 5: Validate the backend dev graph**

Run:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config > /tmp/tgo-backend-dev.yml
./scripts/dev/init.sh --dry-run
```

Expected:

- compose config succeeds
- `/tmp/tgo-backend-dev.yml` includes `migrate-api` through `migrate-device`
- dry-run prints the intended migration order without touching containers

- [ ] **Step 6: Commit the backend dev override**

Run:

```bash
git add docker-compose.dev.yml .env.dev.example scripts/dev/wait-for.sh scripts/dev/init.sh
git commit -m "feat: add backend docker compose dev workflow"
```

### Task 3: Containerize the frontend dev servers and isolate optional tooling with profiles

**Files:**
- Modify: `docker-compose.dev.yml`
- Test: `docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config`

- [ ] **Step 1: Prove the frontend services are still production-style**

Run:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config | rg "node:20-alpine|yarn dev --host 0.0.0.0 --port 5173|yarn dev --host 0.0.0.0 --port 5174" -n
```

Expected: no matches.

- [ ] **Step 2: Override `tgo-web` and `tgo-widget-js` to run Vite inside dev containers**

In `docker-compose.dev.yml`, override both frontend services to use `node:20-alpine`, bind-mounted source, and named `node_modules` volumes.

Use this structure:

```yaml
tgo-web:
  image: node:20-alpine
  working_dir: /app
  env_file:
    - .env.dev
  volumes:
    - ./repos/tgo-web:/app
    - tgo-web-node-modules:/app/node_modules
  ports:
    - "${TGO_WEB_PORT:-5173}:5173"
  command:
    - sh
    - -lc
    - |
      if [ ! -d node_modules/vite ]; then
        yarn install --frozen-lockfile --non-interactive --network-timeout 600000
      fi
      yarn dev --host 0.0.0.0 --port 5173
```

Mirror that pattern for `tgo-widget-js` on port `5174`.

- [ ] **Step 3: Put optional tools behind clear dev profiles**

In `docker-compose.dev.yml`:

- keep the core stack unprofiled
- put `flower` and `adminer` behind `monitoring`
- keep `tgo-device-control-agentos` behind `agentos`

Do not hide core application services behind profiles; `make dev` must still bring up the full app stack by default.

- [ ] **Step 4: Validate the frontend and profile wiring**

Run:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config > /tmp/tgo-frontend-dev.yml
rg -n "node:20-alpine|tgo-web-node-modules|tgo-widget-node-modules|monitoring|agentos" /tmp/tgo-frontend-dev.yml
```

Expected: all five patterns are present.

- [ ] **Step 5: Commit the frontend dev container changes**

Run:

```bash
git add docker-compose.dev.yml
git commit -m "feat: run frontend dev servers in docker compose"
```

### Task 4: Replace the root Makefile with one-command orchestration

**Files:**
- Modify: `Makefile`
- Test: `make help`

- [ ] **Step 1: Capture the legacy Makefile contract**

Run:

```bash
make help | rg "infra-up|migrate|dev-api|dev-web|dev-all|stop-all" -n
```

Expected: multiple matches, confirming the current workflow is still fragmented.

- [ ] **Step 2: Rewrite the root command surface around Compose**

Refactor `Makefile` down to these primary targets:

- `dev`
- `down`
- `logs`
- `ps`
- `restart`
- `clean`

Use a single Compose helper:

```make
ENV_FILE ?= .env.dev
COMPOSE := docker compose --env-file $(ENV_FILE) -f docker-compose.yml -f docker-compose.dev.yml
```

Define the default full-stack service list:

```make
DEV_SERVICES := postgres redis wukongim tgo-rag tgo-rag-worker tgo-rag-beat tgo-ai tgo-plugin-runtime tgo-device-control tgo-platform tgo-workflow tgo-workflow-worker tgo-api tgo-web tgo-widget-js
INFRA_SERVICES := postgres redis wukongim
DISABLE_LIST := $(strip $(subst ',', ,$(DISABLE)))
RUN_SERVICES := $(filter-out $(DISABLE_LIST),$(DEV_SERVICES))
```

- [ ] **Step 3: Implement `make dev` as the only primary startup path**

Wire `make dev` to do the full chain:

```make
dev: check-env
	@$(COMPOSE) build tgo-rag tgo-ai tgo-api tgo-plugin-runtime tgo-device-control tgo-platform tgo-workflow
	@$(COMPOSE) up -d $(INFRA_SERVICES)
	@ENV_FILE=$(ENV_FILE) ./scripts/dev/init.sh
	@$(COMPOSE) up -d $(RUN_SERVICES)
	@echo "TGO dev environment is ready."
```

Add `PROFILES` support by appending `--profile <name>` flags when present, and implement:

- `make down`
- `make logs SERVICE=<name>`
- `make ps`
- `make restart SERVICE=<name>`
- `make clean`

Remove the old host-managed `install*`, `migrate*`, `dev-*`, `infra-*`, and `stop-all` targets from the root workflow.

- [ ] **Step 4: Validate the new command surface**

Run:

```bash
make help
make dev -n
```

Expected:

- help shows the new minimal command set
- dry-run shows a build step, an infra `up -d`, `scripts/dev/init.sh`, and the final `up -d $(RUN_SERVICES)`
- no legacy host-start targets are advertised

- [ ] **Step 5: Commit the Makefile rewrite**

Run:

```bash
git add Makefile
git commit -m "refactor: replace legacy dev make targets"
```

### Task 5: Update the docs and add a regression guard for the new workflow

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `AGENTS.md`
- Create: `scripts/test-dev-environment.sh`
- Test: `scripts/test-dev-environment.sh`

- [ ] **Step 1: Find the stale startup instructions**

Run:

```bash
rg -n "infra-up|make migrate|dev-api|dev-web|dev-all|install-backend|install-frontend" README.md README_CN.md AGENTS.md
```

Expected: multiple matches.

- [ ] **Step 2: Rewrite the docs around the new happy path**

Update the root docs so the local-development quick start is:

```bash
cp .env.dev.example .env.dev
make dev
```

Document advanced trimming as secondary usage, for example:

```bash
make dev DISABLE=flower,adminer
make dev PROFILES=monitoring
```

Update the root workflow in `AGENTS.md` to replace:

- `make infra-up`
- `make migrate`
- `make dev-api`
- `make dev-all`

with the new `make dev` path.

- [ ] **Step 3: Add a repo-local regression script**

Create `scripts/test-dev-environment.sh` using the same style as the existing root validation scripts.

The script should assert all of the following:

- `docker-compose.source.yml` is gone
- `docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config` succeeds
- `make help` contains `make dev`, `make down`, `make logs`, `make ps`, `make restart`, `make clean`
- `make help` does not advertise `infra-up`, `migrate`, `dev-api`, `dev-all`, or `stop-all`

- [ ] **Step 4: Run the regression script**

Run:

```bash
chmod +x scripts/test-dev-environment.sh
./scripts/test-dev-environment.sh
```

Expected: all checks pass.

- [ ] **Step 5: Commit the docs and regression guard**

Run:

```bash
git add README.md README_CN.md AGENTS.md scripts/test-dev-environment.sh
git commit -m "docs: document the new docker compose dev flow"
```

### Task 6: Verify the new workflow end-to-end before declaring success

**Files:**
- Verify: `docker-compose.yml`
- Verify: `docker-compose.dev.yml`
- Verify: `Makefile`
- Verify: `scripts/dev/init.sh`
- Verify: `scripts/test-dev-environment.sh`

- [ ] **Step 1: Start from a clean dev env file**

Run:

```bash
if [ ! -f .env.dev ]; then cp .env.dev.example .env.dev; fi
```

Expected: `.env.dev` exists for Compose interpolation and container env injection.

- [ ] **Step 2: Run the full startup flow**

Run:

```bash
make dev
```

Expected:

- local Python images build successfully
- `postgres`, `redis`, and `wukongim` start first
- `scripts/dev/init.sh` runs all migration one-shots successfully
- the full stack comes up without manual per-service commands

- [ ] **Step 3: Confirm service health and process state**

Run:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml ps
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8081/health
curl -fsS http://localhost:8082/health
curl -I http://localhost:5173
curl -I http://localhost:5174
```

Expected:

- core services are `running` or `healthy`
- API, AI, and RAG health endpoints return success
- both frontend ports return HTTP headers from the Vite dev servers

- [ ] **Step 4: Verify the operational escape hatches**

Run:

```bash
timeout 5 make logs SERVICE=tgo-api || true
make restart SERVICE=tgo-ai
./scripts/test-dev-environment.sh
```

Expected:

- logs stream from the requested service for a few seconds without error
- restart recreates only `tgo-ai`
- the regression script still passes after a real startup

- [ ] **Step 5: Perform one manual reload check per stack type**

Backend:

```bash
touch repos/tgo-api/app/main.py
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml logs --since=20s tgo-api
```

Expected: the API container logs show a reload cycle after the file timestamp changes.

Frontend:

```bash
echo "// dev-hmr-check $(date +%s)" >> repos/tgo-web/src/main.tsx
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml logs --since=20s tgo-web
python3 - <<'PY'
from pathlib import Path
path = Path("repos/tgo-web/src/main.tsx")
lines = path.read_text().splitlines()
path.write_text("\n".join(line for line in lines if not line.startswith("// dev-hmr-check ")) + "\n")
PY
```

Expected: the Vite dev server detects the file change. Revert the temporary line immediately after confirming the log output.

- [ ] **Step 6: Shut the environment down cleanly**

Run:

```bash
make down
```

Expected: the dev stack stops without leaving stray host processes behind.

- [ ] **Step 7: Create the final implementation commit**

Run:

```bash
git status --short
git add -A docker-compose.yml docker-compose.dev.yml docker-compose.source.yml Makefile .env.dev.example scripts/dev scripts/test-dev-environment.sh README.md README_CN.md AGENTS.md
git commit -m "feat: simplify local development with make dev"
```

Expected: the working tree is clean except for any unrelated user-owned changes outside this plan.
