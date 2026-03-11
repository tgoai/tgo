---
name: streaming-protocol-check
description: Check streaming protocol consistency across all producer and consumer services. Trigger when modifying code related to streaming, SSE, WuKongIM, json-render, or MixedStreamParser — lists all files in tgo-ai (producer), tgo-api (relay), tgo-web, tgo-widget-js, and tgo-widget-miniprogram (consumers) that handle the same protocol and may need coordinated updates.
---

# streaming-protocol-check

## Purpose
Check streaming protocol changes for consistency across all consuming services.

## Trigger
When streaming, SSE, WuKongIM, or json-render code is modified.

## What it does
1. Detects changes in streaming-related paths
2. Lists all files across services that handle the same protocol
3. Highlights potential inconsistencies

## Usage
```bash
bash .skills/streaming-protocol-check/scripts/check.sh
```
