# tgo-widget-js — AGENTS.md

> Stack: React 18 + TypeScript 5.6 + Vite 5 + Emotion + Zustand 5 · Port: 5174
> Sister project: `tgo-web` — json-render components must stay in sync

## Rules

- Change order: `types → store → components`
- Message protocol changes must verify both history messages and streaming messages paths
- iframe communication changes must test host-page events
- json-render changes must check if `tgo-web` needs sync, and vice versa
- Styles use Emotion + inline CSSProperties — no Tailwind (that's tgo-web)

## Key Paths

| Area | Files |
|------|-------|
| App init | `src/App.tsx` |
| Chat state/IM | `src/store/chatStore.ts` |
| Platform config | `src/store/platformStore.ts` |
| IM service | `src/services/wukongim.ts` |
| json-render surface | `src/components/jsonRender/JSONRenderSurface.tsx` |
| json-render registry | `src/components/jsonRender/registry.tsx` |
| json-render message | `src/components/messages/JSONRenderMessage.tsx` |
| Message types | `src/types/chat.ts` |
| Message list | `src/components/MessageList.tsx` |
| Message input | `src/components/MessageInput.tsx` |

## Constraints

- `postMessage` event types and payload structure must stay compatible (`tgo:visibility`, `TGO_WIDGET_UNREAD`, `TGO_SHOW_TOAST`, `TGO_WIDGET_CONFIG`)
- Components must not make direct requests — use `services/*` + `store/*`
- Markdown/HTML rendering must keep XSS protection (DOMPurify)
- No Tailwind — use Emotion + CSS variables (`--primary`, `--bg-primary`, `--text-primary`)
- User-visible text should use `i18n/locales/*`

## json-render sync with tgo-web

Differences between the two projects (logic must match):
- **Styles**: widget = inline CSSProperties + CSS vars; web = Tailwind
- **Message types**: widget = `ChatMessage` (`uiParts`, `streamData`); web = `Message` (`metadata.ui_parts`, `metadata.stream_end`)
- **Callbacks**: widget = `onAction(name, context)`; web = `onSendMessage(text)`

## Verify

```bash
# Static
yarn build

# Functional — widget-app calls tgo-api visitor endpoints; use CLI to verify
WIDGET_CLI="node ../tgo-widget-cli/dist/index.js"
$WIDGET_CLI platform info               # platform config API
$WIDGET_CLI channel info                # channel API
$WIDGET_CLI chat history --limit 3      # message history API
$WIDGET_CLI chat send --message "say ok" --no-stream  # chat e2e
```
