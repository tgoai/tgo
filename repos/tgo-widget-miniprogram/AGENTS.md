# tgo-widget-miniprogram — AGENTS.md

> Stack: Pure JS (ES5), WeChat mini-program native components
> Sister project: `tgo-widget-js` (React Web) — json-render logic must stay in sync

## Rules

- All components use `Component({})` — follow mini-program lifecycle (`attached`, `detached`)
- `sendmessage` events do NOT use `bubbles` — rely on manual relay to avoid duplicate triggers
- `action` events use `bubbles: true, composed: true` to reach surface through containers
- json-render changes must stay consistent with `tgo-widget-js`
- When porting from React: Emotion → wxss, `onAction` → `triggerEvent`, Hooks → lifetimes/observers

## Key Paths

| Area | Files |
|------|-------|
| Main component | `src/chat/` |
| Message list | `src/components/message-list/` |
| Message input | `src/components/message-input/` |
| json-render message | `src/components/json-render-message/` |
| json-render surface | `src/components/json-render-surface/` |
| json-render element | `src/components/json-render-element/` |
| Chat state | `src/core/chatStore.js` |
| Platform state | `src/core/platformStore.js` |
| Types | `src/core/types.js` |
| IM service | `src/services/wukongim.js` |
| json-render utils | `src/utils/jsonRender.js` |
| Build script | `tools/build.js` |

## Constraints

- Pure JS only — no TypeScript
- Build: `src/` → `miniprogram_dist/` via `tools/build.js` (includes Babel transpile, zod .cjs fix)
- State management via pub/sub singletons (`chatStore`, `platformStore`)
- Component communication: `properties` + `bindXxx` events + manual `triggerEvent` relay
- Built-in actions (`setState`, `pushState`, `removeState`, `validateForm`) auto-handled — don't register custom handlers for these

## Common Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| zod require error | Mini-program npm doesn't handle .cjs | build.js auto-fixes .cjs → .js |
| sendmessage fires twice | bubbles + manual relay overlap | sendmessage must NOT use bubbles |
| ScrollView not scrolling | scroll-top value unchanged | Alternate 999999/999998 via `_scrollCounter` |

## Verify

```bash
# Static
npm run build

# Functional — same visitor APIs as tgo-widget-js
WIDGET_CLI="node ../tgo-widget-cli/dist/index.js"
$WIDGET_CLI platform info               # platform config API
$WIDGET_CLI chat send --message "say ok" --no-stream  # chat e2e
```
