# ==========================================================
# TGO Development Makefile
# ==========================================================
# This Makefile provides convenient commands for local development.
# All backend services run with hot-reload (uvicorn --reload).
# All frontend services run with Vite HMR.
#
# Quick Start:
#   1. cp .env.dev.example .env.dev
#   2. make install        # Install all dependencies
#   3. make infra-up       # Start infrastructure (PostgreSQL, Redis, WuKongIM)
#   4. make migrate        # Run database migrations
#   5. make dev-api        # Start tgo-api (in one terminal)
#   6. make dev-web        # Start tgo-web (in another terminal)
# ==========================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Environment file for development
ENV_FILE := .env.dev

# Docker compose file for development infrastructure
COMPOSE_DEV := docker-compose.dev.yml

# Service directories
API_DIR := repos/tgo-api
AI_DIR := repos/tgo-ai
RAG_DIR := repos/tgo-rag
PLATFORM_DIR := repos/tgo-platform
WORKFLOW_DIR := repos/tgo-workflow
PLUGIN_DIR := repos/tgo-plugin-runtime
DEVICE_DIR := repos/tgo-device-control
WEB_DIR := repos/tgo-web
WIDGET_DIR := repos/tgo-widget-app

# Development ports (to avoid conflicts)
API_PORT := 8000
AI_PORT := 8081
RAG_PORT := 8082
PLATFORM_PORT := 8003
WORKFLOW_PORT := 8004
PLUGIN_PORT := 8090
DEVICE_PORT := 8085
WEB_PORT := 5173
WIDGET_PORT := 5174

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# ==========================================================
# Help
# ==========================================================
.PHONY: help
help:
	@echo ""
	@echo "$(CYAN)TGO Development Commands$(RESET)"
	@echo "========================="
	@echo ""
	@echo "$(GREEN)Setup:$(RESET)"
	@echo "  make install          Install all service dependencies"
	@echo "  make install-backend  Install backend dependencies (continues on failure)"
	@echo "  make install-frontend Install frontend dependencies"
	@echo "  make install-api      Install tgo-api only"
	@echo "  make install-ai       Install tgo-ai only"
	@echo "  make install-rag      Install tgo-rag only (requires torch)"
	@echo "  make install-<svc>    Install specific service (platform/workflow/plugin/device)"
	@echo ""
	@echo "$(GREEN)Infrastructure (Docker):$(RESET)"
	@echo "  make infra-up         Start PostgreSQL, Redis, WuKongIM"
	@echo "  make infra-down       Stop infrastructure"
	@echo "  make infra-logs       View infrastructure logs"
	@echo "  make infra-ps         Show infrastructure status"
	@echo ""
	@echo "$(GREEN)Database:$(RESET)"
	@echo "  make migrate          Run all database migrations"
	@echo "  make migrate-api      Run tgo-api migrations"
	@echo "  make migrate-ai       Run tgo-ai migrations"
	@echo "  make migrate-rag      Run tgo-rag migrations"
	@echo "  make migrate-platform Run tgo-platform migrations"
	@echo "  make migrate-workflow Run tgo-workflow migrations"
	@echo "  make migrate-plugin   Run tgo-plugin-runtime migrations"
	@echo "  make migrate-device   Run tgo-device-control migrations"
	@echo ""
	@echo "$(GREEN)Backend Services (run in separate terminals):$(RESET)"
	@echo "  make dev-backend      Start all backend services (requires tmux)"
	@echo "  make dev-api          Start tgo-api        (port $(API_PORT))"
	@echo "  make dev-ai           Start tgo-ai         (port $(AI_PORT))"
	@echo "  make dev-rag          Start tgo-rag        (port $(RAG_PORT))"
	@echo "  make dev-platform     Start tgo-platform   (port $(PLATFORM_PORT))"
	@echo "  make dev-workflow     Start tgo-workflow   (port $(WORKFLOW_PORT))"
	@echo "  make dev-plugin       Start tgo-plugin     (port $(PLUGIN_PORT))"
	@echo "  make dev-device       Start tgo-device     (port $(DEVICE_PORT))"
	@echo ""
	@echo "$(GREEN)Frontend Services (run in separate terminals):$(RESET)"
	@echo "  make dev-frontend     Start all frontend services (requires tmux)"
	@echo "  make dev-web          Start tgo-web        (port $(WEB_PORT))"
	@echo "  make dev-widget       Start tgo-widget-app (port $(WIDGET_PORT))"
	@echo ""
	@echo "$(GREEN)Combined:$(RESET)"
	@echo "  make dev-all          Start all services in background"
	@echo "  make stop-all         Stop all background services"
	@echo ""
	@echo "$(GREEN)Celery Workers:$(RESET)"
	@echo "  make dev-rag-worker   Start RAG Celery worker"
	@echo "  make dev-wf-worker    Start Workflow Celery worker"
	@echo ""
	@echo "$(GREEN)Utilities:$(RESET)"
	@echo "  make check-env        Check if .env.dev exists"
	@echo "  make logs SERVICE=x   View logs for a service (e.g., make logs SERVICE=postgres)"
	@echo "  make shell SERVICE=x  Open shell in a container"
	@echo "  make psql             Open PostgreSQL CLI"
	@echo "  make redis-cli        Open Redis CLI"
	@echo ""

# ==========================================================
# Environment Check
# ==========================================================
.PHONY: check-env
check-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found$(RESET)"; \
		echo "$(YELLOW)Run: cp .env.dev.example .env.dev$(RESET)"; \
		exit 1; \
	fi

# ==========================================================
# Infrastructure Commands
# ==========================================================
.PHONY: infra-up infra-down infra-logs infra-ps

infra-up:
	@echo "$(CYAN)Starting development infrastructure...$(RESET)"
	@docker compose -f $(COMPOSE_DEV) up -d
	@echo "$(GREEN)Infrastructure started!$(RESET)"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Redis:      localhost:6379"
	@echo "  WuKongIM:   localhost:5001 (API), 5100 (TCP), 5200 (WS)"

infra-down:
	@echo "$(CYAN)Stopping development infrastructure...$(RESET)"
	@docker compose -f $(COMPOSE_DEV) down
	@echo "$(GREEN)Infrastructure stopped$(RESET)"

infra-logs:
	@docker compose -f $(COMPOSE_DEV) logs -f

infra-ps:
	@docker compose -f $(COMPOSE_DEV) ps

# ==========================================================
# Dependency Installation
# ==========================================================
.PHONY: install install-backend install-frontend install-api install-ai install-rag install-platform install-workflow install-plugin install-device

install: install-backend install-frontend
	@echo "$(GREEN)Dependency installation completed!$(RESET)"

install-backend:
	@echo "$(CYAN)Installing backend dependencies...$(RESET)"
	@echo "$(YELLOW)Note: Some services (e.g., tgo-rag) may fail on certain platforms due to torch compatibility.$(RESET)"
	@echo "$(YELLOW)You can install services individually: make install-api, make install-ai, etc.$(RESET)"
	@echo ""
	@$(MAKE) install-api || echo "$(RED)tgo-api install failed$(RESET)"
	@$(MAKE) install-ai || echo "$(RED)tgo-ai install failed$(RESET)"
	@$(MAKE) install-rag || echo "$(YELLOW)tgo-rag install failed (torch may not be compatible with your platform)$(RESET)"
	@$(MAKE) install-platform || echo "$(RED)tgo-platform install failed$(RESET)"
	@$(MAKE) install-workflow || echo "$(RED)tgo-workflow install failed$(RESET)"
	@$(MAKE) install-plugin || echo "$(RED)tgo-plugin-runtime install failed$(RESET)"
	@$(MAKE) install-device || echo "$(RED)tgo-device-control install failed$(RESET)"
	@echo "$(GREEN)Backend installation completed$(RESET)"

install-api:
	@echo "  $(CYAN)Installing tgo-api...$(RESET)"
	@cd $(API_DIR) && poetry install --no-root

install-ai:
	@echo "  $(CYAN)Installing tgo-ai...$(RESET)"
	@cd $(AI_DIR) && poetry install --no-root

install-rag:
	@echo "  $(CYAN)Installing tgo-rag...$(RESET)"
	@cd $(RAG_DIR) && poetry install --no-root

install-platform:
	@echo "  $(CYAN)Installing tgo-platform...$(RESET)"
	@cd $(PLATFORM_DIR) && poetry install --no-root

install-workflow:
	@echo "  $(CYAN)Installing tgo-workflow...$(RESET)"
	@cd $(WORKFLOW_DIR) && poetry install --no-root

install-plugin:
	@echo "  $(CYAN)Installing tgo-plugin-runtime...$(RESET)"
	@cd $(PLUGIN_DIR) && poetry install --no-root

install-device:
	@echo "  $(CYAN)Installing tgo-device-control...$(RESET)"
	@if [ -d $(DEVICE_DIR) ]; then \
		cd $(DEVICE_DIR) && poetry install --no-root; \
	else \
		echo "$(YELLOW)tgo-device-control not found, skipping$(RESET)"; \
	fi

install-frontend:
	@echo "$(CYAN)Installing frontend dependencies...$(RESET)"
	@cd $(WEB_DIR) && npm install
	@cd $(WIDGET_DIR) && npm install
	@echo "$(GREEN)Frontend dependencies installed$(RESET)"

# ==========================================================
# Database Migrations
# ==========================================================
.PHONY: migrate migrate-api migrate-ai migrate-rag migrate-platform migrate-workflow migrate-plugin migrate-device

migrate: check-env migrate-api migrate-ai migrate-rag migrate-platform migrate-workflow migrate-plugin migrate-device
	@echo "$(GREEN)All migrations completed!$(RESET)"

migrate-api: check-env
	@echo "$(CYAN)Running tgo-api migrations...$(RESET)"
	@cd $(API_DIR) && set -a && source ../../$(ENV_FILE) && set +a && PYTHONPATH=. poetry run alembic upgrade head

migrate-ai: check-env
	@echo "$(CYAN)Running tgo-ai migrations...$(RESET)"
	@cd $(AI_DIR) && set -a && source ../../$(ENV_FILE) && set +a && PYTHONPATH=. poetry run alembic upgrade head

migrate-rag: check-env
	@echo "$(CYAN)Running tgo-rag migrations...$(RESET)"
	@cd $(RAG_DIR) && set -a && source ../../$(ENV_FILE) && set +a && PYTHONPATH=. poetry run alembic upgrade head

migrate-platform: check-env
	@echo "$(CYAN)Running tgo-platform migrations...$(RESET)"
	@cd $(PLATFORM_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		API_BASE_URL=http://localhost:$(API_PORT) \
		PYTHONPATH=. poetry run alembic upgrade head

migrate-workflow: check-env
	@echo "$(CYAN)Running tgo-workflow migrations...$(RESET)"
	@cd $(WORKFLOW_DIR) && set -a && source ../../$(ENV_FILE) && set +a && PYTHONPATH=. poetry run alembic upgrade head

migrate-plugin: check-env
	@echo "$(CYAN)Running tgo-plugin-runtime migrations...$(RESET)"
	@cd $(PLUGIN_DIR) && set -a && source ../../$(ENV_FILE) && set +a && PYTHONPATH=. poetry run alembic upgrade head

migrate-device: check-env
	@echo "$(CYAN)Running tgo-device-control migrations...$(RESET)"
	@if [ -d $(DEVICE_DIR) ]; then \
		cd $(DEVICE_DIR) && \
		set -a && source ../../$(ENV_FILE) && set +a && \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		PYTHONPATH=. poetry run alembic upgrade head; \
	else \
		echo "$(YELLOW)tgo-device-control not found, skipping$(RESET)"; \
	fi

# ==========================================================
# Backend Development Servers
# ==========================================================
.PHONY: dev-api dev-ai dev-rag dev-platform dev-workflow dev-plugin dev-device

dev-api: check-env
	@echo "$(CYAN)Starting tgo-api on port $(API_PORT)...$(RESET)"
	@cd $(API_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		PORT=$(API_PORT) \
		REDIS_URL=redis://localhost:6379/0 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		poetry run uvicorn app.main:app --host 0.0.0.0 --port $(API_PORT) --reload

dev-ai: check-env
	@echo "$(CYAN)Starting tgo-ai on port $(AI_PORT)...$(RESET)"
	@cd $(AI_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		PORT=$(AI_PORT) \
		REDIS_URL=redis://localhost:6379/1 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		API_SERVICE_URL=http://localhost:$(API_PORT) \
		RAG_SERVICE_URL=http://localhost:$(RAG_PORT) \
		WORKFLOW_SERVICE_URL=http://localhost:$(WORKFLOW_PORT) \
		PLUGIN_RUNTIME_URL=http://localhost:$(PLUGIN_PORT) \
		DEVICE_CONTROL_SERVICE_URL=http://localhost:$(DEVICE_PORT) \
		poetry run uvicorn app.main:app --host 0.0.0.0 --port $(AI_PORT) --reload

dev-rag: check-env
	@echo "$(CYAN)Starting tgo-rag on port $(RAG_PORT)...$(RESET)"
	@cd $(RAG_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		PORT=$(RAG_PORT) \
		REDIS_URL=redis://localhost:6379/2 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		poetry run uvicorn src.rag_service.main:app --host 0.0.0.0 --port $(RAG_PORT) --reload

dev-platform: check-env
	@echo "$(CYAN)Starting tgo-platform on port $(PLATFORM_PORT)...$(RESET)"
	@cd $(PLATFORM_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		PORT=$(PLATFORM_PORT) \
		REDIS_URL=redis://localhost:6379/0 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		API_BASE_URL=http://localhost:$(API_PORT) \
		poetry run uvicorn app.main:app --host 0.0.0.0 --port $(PLATFORM_PORT) --reload

dev-workflow: check-env
	@echo "$(CYAN)Starting tgo-workflow on port $(WORKFLOW_PORT)...$(RESET)"
	@cd $(WORKFLOW_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		PORT=$(WORKFLOW_PORT) \
		REDIS_URL=redis://localhost:6379/2 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		AI_SERVICE_URL=http://localhost:$(AI_PORT) \
		poetry run uvicorn app.main:app --host 0.0.0.0 --port $(WORKFLOW_PORT) --reload

dev-plugin: check-env
	@echo "$(CYAN)Starting tgo-plugin-runtime on port $(PLUGIN_PORT)...$(RESET)"
	@cd $(PLUGIN_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		PORT=$(PLUGIN_PORT) \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		AI_SERVICE_URL=http://localhost:$(AI_PORT) \
		poetry run uvicorn app.main:app --host 0.0.0.0 --port $(PLUGIN_PORT) --reload

dev-device: check-env
	@echo "$(CYAN)Starting tgo-device-control on port $(DEVICE_PORT)...$(RESET)"
	@if [ -d $(DEVICE_DIR) ]; then \
		cd $(DEVICE_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
			PORT=$(DEVICE_PORT) \
			REDIS_URL=redis://localhost:6379/3 \
			DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
			AI_SERVICE_URL=http://localhost:$(AI_PORT) \
			API_SERVICE_URL=http://localhost:$(API_PORT) \
			poetry run uvicorn app.main:app --host 0.0.0.0 --port $(DEVICE_PORT) --reload; \
	else \
		echo "$(RED)tgo-device-control not found$(RESET)"; \
		exit 1; \
	fi

# ==========================================================
# Batch Start Commands (requires tmux)
# ==========================================================
.PHONY: dev-backend dev-frontend dev-all

dev-backend: check-env
	@echo "$(CYAN)Starting all backend services in background...$(RESET)"
	@$(MAKE) dev-api > /dev/null 2>&1 & \
	$(MAKE) dev-ai > /dev/null 2>&1 & \
	$(MAKE) dev-rag > /dev/null 2>&1 & \
	$(MAKE) dev-platform > /dev/null 2>&1 & \
	$(MAKE) dev-workflow > /dev/null 2>&1 & \
	$(MAKE) dev-plugin > /dev/null 2>&1 & \
	$(MAKE) dev-device > /dev/null 2>&1 & \
	echo "$(GREEN)Backend services started in background.$(RESET)"
	@echo "$(YELLOW)Use 'ps aux | grep uvicorn' to see processes or 'make stop-all' to kill them.$(RESET)"

dev-frontend: check-env
	@echo "$(CYAN)Starting all frontend services in background...$(RESET)"
	@$(MAKE) dev-web > /dev/null 2>&1 & \
	$(MAKE) dev-widget > /dev/null 2>&1 & \
	echo "$(GREEN)Frontend services started in background.$(RESET)"

dev-all: dev-backend dev-frontend

.PHONY: stop-all
stop-all:
	@echo "$(YELLOW)Stopping all local development services...$(RESET)"
	@pkill -f "uvicorn.*app.main:app" || true
	@pkill -f "uvicorn.*src.rag_service.main:app" || true
	@pkill -f "vite" || true
	@pkill -f "celery" || true
	@echo "$(GREEN)All services stopped.$(RESET)"

# ==========================================================
# Frontend Development Servers
# ==========================================================
.PHONY: dev-web dev-widget

dev-web: check-env
	@echo "$(CYAN)Starting tgo-web on port $(WEB_PORT)...$(RESET)"
	@cd $(WEB_DIR) && \
		VITE_API_BASE_URL=http://localhost:$(API_PORT) \
		VITE_DEBUG_MODE=true \
		npm run dev -- --port $(WEB_PORT)

dev-widget: check-env
	@echo "$(CYAN)Starting tgo-widget-app on port $(WIDGET_PORT)...$(RESET)"
	@cd $(WIDGET_DIR) && \
		VITE_API_BASE=http://localhost:$(API_PORT) \
		npm run dev -- --port $(WIDGET_PORT)

# ==========================================================
# Celery Workers
# ==========================================================
.PHONY: dev-rag-worker dev-wf-worker

dev-rag-worker: check-env
	@echo "$(CYAN)Starting RAG Celery worker...$(RESET)"
	@cd $(RAG_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		REDIS_URL=redis://localhost:6379/2 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		poetry run celery -A src.rag_service.tasks.celery_app worker \
			--loglevel=info \
			-Q document_processing,embedding,website_crawling,qa_processing,celery

dev-wf-worker: check-env
	@echo "$(CYAN)Starting Workflow Celery worker...$(RESET)"
	@cd $(WORKFLOW_DIR) && set -a && source ../../$(ENV_FILE) && set +a && \
		REDIS_URL=redis://localhost:6379/2 \
		DATABASE_URL=postgresql+asyncpg://tgo:tgo@localhost:5432/tgo \
		AI_SERVICE_URL=http://localhost:$(AI_PORT) \
		poetry run celery -A celery_app.celery worker --loglevel=info -Q workflow

# ==========================================================
# Utility Commands
# ==========================================================
.PHONY: logs shell psql redis-cli clean

logs:
	@if [ -z "$(SERVICE)" ]; then \
		docker compose -f $(COMPOSE_DEV) logs -f; \
	else \
		docker compose -f $(COMPOSE_DEV) logs -f $(SERVICE); \
	fi

shell:
	@if [ -z "$(SERVICE)" ]; then \
		echo "$(RED)Usage: make shell SERVICE=postgres$(RESET)"; \
		exit 1; \
	fi
	@docker compose -f $(COMPOSE_DEV) exec $(SERVICE) sh

psql:
	@docker compose -f $(COMPOSE_DEV) exec postgres psql -U tgo -d tgo

redis-cli:
	@docker compose -f $(COMPOSE_DEV) exec redis redis-cli

clean:
	@echo "$(YELLOW)Cleaning up...$(RESET)"
	@docker compose -f $(COMPOSE_DEV) down -v
	@echo "$(GREEN)Cleanup complete$(RESET)"
