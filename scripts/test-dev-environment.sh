#!/bin/bash
# Regression checks for the root-level Docker Compose dev workflow.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
  local test_name="$1"
  local test_cmd="$2"

  echo -n "Testing: $test_name ... "
  if eval "$test_cmd" > /dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo -e "${RED}FAIL${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
  fi
}

if [ ! -f .env.dev ] && [ -f .env.dev.example ]; then
  cp .env.dev.example .env.dev
fi

HELP_OUTPUT="$(make help 2>/dev/null)"
SUMMARY_OUTPUT="$(ENV_FILE=.env.dev RUNNING_SERVICES=$'postgres\nredis\ntgo-api\nadminer' ./scripts/dev/summary.sh 2>/dev/null || true)"

echo "========================================="
echo "  Dev Environment Workflow Regression"
echo "========================================="
echo ""

run_test "docker-compose.source.yml removed" \
  "[ ! -e docker-compose.source.yml ]"

run_test "merged compose config is valid" \
  "docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml config"

run_test "help advertises make dev" \
  "printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'make dev'"

run_test "help advertises make down" \
  "printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'make down'"

run_test "help advertises make logs" \
  "printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'make logs'"

run_test "help advertises make ps" \
  "printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'make ps'"

run_test "help advertises make restart" \
  "printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'make restart'"

run_test "help advertises make clean" \
  "printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'make clean'"

run_test "help no longer advertises infra-up" \
  "! printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'infra-up'"

run_test "help no longer advertises migrate" \
  "! printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'make migrate'"

run_test "help no longer advertises dev-api" \
  "! printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'dev-api'"

run_test "help no longer advertises dev-all" \
  "! printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'dev-all'"

run_test "help no longer advertises stop-all" \
  "! printf '%s\n' \"$HELP_OUTPUT\" | grep -q 'stop-all'"

run_test "dev summary script prints postgres login info" \
  "printf '%s\n' \"$SUMMARY_OUTPUT\" | grep -q 'Postgres: postgresql://tgo:tgo@localhost:5432/tgo'"

run_test "dev summary script prints adminer access info" \
  "printf '%s\n' \"$SUMMARY_OUTPUT\" | grep -q 'Adminer: http://localhost:8089'"

run_test "dev summary script prints API access info" \
  "printf '%s\n' \"$SUMMARY_OUTPUT\" | grep -q 'API: http://localhost:8000'"

run_test "dev summary only shows running services" \
  "! printf '%s\n' \"$SUMMARY_OUTPUT\" | grep -q 'AI: http://localhost:8081'"

run_test "dev summary can inspect running compose services" \
  "ENV_FILE=.env.dev ./scripts/dev/summary.sh >/dev/null"

run_test "make dev prints the dev summary" \
  "rg -q './scripts/dev/summary.sh' Makefile"

echo ""
echo "========================================="
echo "  Results"
echo "========================================="
echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${RED}$TESTS_FAILED${NC}"

if [ "$TESTS_FAILED" -ne 0 ]; then
  echo -e "${YELLOW}Dev workflow regression checks failed${NC}"
  exit 1
fi

echo -e "${GREEN}All dev workflow regression checks passed${NC}"
