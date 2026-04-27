# ==========================================================
# TGO Development Makefile
# ==========================================================
# Primary local workflow:
#   cp .env.dev.example .env.dev
#   make dev
# ==========================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

empty :=
space := $(empty) $(empty)
comma := ,

ENV_FILE ?= .env.dev
COMPOSE_BASE := docker compose --env-file $(ENV_FILE) -f docker-compose.yml -f docker-compose.dev.yml
PROFILES_LIST := $(strip $(subst $(comma),$(space),$(PROFILES)))
PROFILE_FLAGS := $(foreach profile,$(PROFILES_LIST),--profile $(profile))
COMPOSE := $(COMPOSE_BASE) $(PROFILE_FLAGS)
KNOWN_PROFILES := monitoring agentos
KNOWN_PROFILE_FLAGS := $(foreach profile,$(KNOWN_PROFILES),--profile $(profile))
COMPOSE_ALL_PROFILES := $(COMPOSE_BASE) $(KNOWN_PROFILE_FLAGS)
BUILDKIT_PROGRESS ?= auto

INFRA_SERVICES := postgres redis wukongim
BUILD_SERVICES := tgo-rag tgo-ai tgo-api tgo-plugin-runtime tgo-device-control tgo-platform tgo-workflow
CORE_APP_SERVICES := tgo-rag tgo-rag-worker tgo-rag-beat tgo-ai tgo-plugin-runtime tgo-device-control tgo-platform tgo-workflow tgo-workflow-worker tgo-api tgo-web tgo-widget-js
MONITORING_SERVICES := tgo-celery-flower adminer
AGENTOS_SERVICES := tgo-device-control-agentos
PROFILE_SERVICES := $(if $(filter monitoring,$(PROFILES_LIST)),$(MONITORING_SERVICES),) $(if $(filter agentos,$(PROFILES_LIST)),$(AGENTOS_SERVICES),)
DISABLE_LIST := $(strip $(subst $(comma),$(space),$(DISABLE)))
RUN_SERVICES := $(filter-out $(DISABLE_LIST),$(CORE_APP_SERVICES) $(PROFILE_SERVICES))

CYAN := \033[36m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

.PHONY: help check-env dev down logs ps restart clean

help:
	@echo ""
	@echo "$(CYAN)TGO Dev Commands$(RESET)"
	@echo "================="
	@echo ""
	@echo "  make dev                       Build backend images, run init, and launch the dev stack"
	@echo "  make down                      Stop the dev stack"
	@echo "  make logs [SERVICE=tgo-api]    Follow logs for all services or one service"
	@echo "  make ps                        Show current compose service status"
	@echo "  make restart SERVICE=tgo-ai    Restart one service"
	@echo "  make clean                     Stop the stack and remove named volumes"
	@echo ""
	@echo "Advanced:"
	@echo "  make dev PROFILES=monitoring   Also start monitoring helpers"
	@echo "  make dev PROFILES=agentos      Also start AgentOS"
	@echo "  make dev DISABLE=tgo-rag-beat,tgo-workflow-worker"
	@echo ""

check-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(RED)Error: $(ENV_FILE) not found$(RESET)"; \
		echo "$(YELLOW)Run: cp .env.dev.example $(ENV_FILE)$(RESET)"; \
		exit 1; \
	fi

dev: check-env
	@echo "$(CYAN)Building local backend images...$(RESET)"
	@COMPOSE_PARALLEL_LIMIT=1 BUILDKIT_PROGRESS=$(BUILDKIT_PROGRESS) $(COMPOSE) build $(BUILD_SERVICES)
	@echo "$(CYAN)Starting infrastructure...$(RESET)"
	@$(COMPOSE) up -d $(INFRA_SERVICES)
	@echo "$(CYAN)Running development init flow...$(RESET)"
	@ENV_FILE=$(ENV_FILE) ./scripts/dev/init.sh
	@echo "$(CYAN)Starting application services...$(RESET)"
	@$(COMPOSE) up -d $(RUN_SERVICES)
	@ENV_FILE=$(ENV_FILE) PROFILES='$(PROFILES)' ./scripts/dev/summary.sh

down: check-env
	@$(COMPOSE_ALL_PROFILES) down --remove-orphans

logs: check-env
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) logs -f $(SERVICE); \
	else \
		$(COMPOSE) logs -f $(INFRA_SERVICES) $(RUN_SERVICES); \
	fi

ps: check-env
	@$(COMPOSE) ps

restart: check-env
	@if [ -z "$(SERVICE)" ]; then \
		echo "$(RED)Usage: make restart SERVICE=tgo-ai$(RESET)"; \
		exit 1; \
	fi
	@$(COMPOSE) restart $(SERVICE)

clean: check-env
	@$(COMPOSE_ALL_PROFILES) down -v --remove-orphans
