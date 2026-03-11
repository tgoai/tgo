---
name: code-change-verification
description: Run lint, type-check, and build verification for changed services after code modifications are complete. Trigger after any code change to repos/*/ — auto-detects which services were touched via git diff and runs the appropriate static checks (mypy/flake8 for Python, type-check/lint/build for TypeScript, go vet for Go).
---

# code-change-verification

## Purpose
Auto-detect which services were changed and run their lint/type-check/build verification.

## Trigger
After any code modification is complete.

## What it does
1. Reads `git diff --name-only` to identify changed service directories
2. Runs the appropriate verification command per service:
   - Python services → `poetry run mypy app && poetry run flake8 app`
   - tgo-web → `yarn type-check && yarn lint && yarn build`
   - tgo-widget-js → `npm run build`
   - tgo-device-agent → `go vet ./...`
3. Outputs pass/fail per service

## Usage
```bash
bash .skills/code-change-verification/scripts/verify.sh
```
