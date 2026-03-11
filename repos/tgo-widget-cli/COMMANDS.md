# tgo-widget CLI Commands

## Global Options

```
-s, --server <url>     API server URL
-k, --api-key <key>    Platform API Key
-o, --output <format>  Output format: json (default) | table | compact
-v, --verbose          Verbose output
```

## Commands

### init

Register as a visitor and save configuration.

```bash
tgo-widget init --api-key <key> --server <url> [--name <n>] [--email <e>] [--phone <p>]
```

### chat send

Send a message and get AI response (SSE streaming by default).

```bash
tgo-widget chat send --message "Hello"
tgo-widget chat send --message "Hello" --no-stream    # JSON response
```

### chat send-ws

Send a message via WuKongIM WebSocket (raw IM, no AI reply).

```bash
tgo-widget chat send-ws --message "Hello"
```

### chat listen

Listen for incoming messages via WuKongIM WebSocket (JSONL output).

```bash
tgo-widget chat listen
tgo-widget chat listen --events    # Include custom events
```

### chat history

Get message history.

```bash
tgo-widget chat history
tgo-widget chat history --limit 50 --start-seq 100
```

### chat upload

Upload a file to the chat.

```bash
tgo-widget chat upload /path/to/file.pdf
```

### platform info

Get platform information.

```bash
tgo-widget platform info
```

### channel info

Get channel information.

```bash
tgo-widget channel info
tgo-widget channel info --channel-id <id> --channel-type 251
```

### activity record

Record a visitor activity.

```bash
tgo-widget activity record --type page_view --title "Visited pricing page"
tgo-widget activity record --type custom_event --title "Clicked CTA" --description "Hero section"
```

### whoami

Show current visitor configuration.

```bash
tgo-widget whoami
```

### reset

Clear saved configuration.

```bash
tgo-widget reset
```

### mcp serve

Start MCP Server (stdio transport).

```bash
tgo-widget mcp serve
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `tgo_widget_init` | Register as visitor |
| `tgo_widget_chat_send` | Send message + get AI response |
| `tgo_widget_chat_send_ws` | Send via WebSocket (raw IM) |
| `tgo_widget_chat_history` | Get message history |
| `tgo_widget_chat_upload` | Upload a file |
| `tgo_widget_platform_info` | Get platform info |
| `tgo_widget_channel_info` | Get channel info |
| `tgo_widget_activity_record` | Record visitor activity |
| `tgo_widget_whoami` | Show current config |
| `tgo_widget_reset` | Clear config |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TGO_WIDGET_SERVER` | API server URL |
| `TGO_WIDGET_API_KEY` | Platform API Key |
| `TGO_WIDGET_OUTPUT` | Default output format |
| `TGO_DEBUG` | Enable debug logging |

## Configuration

Config is stored at `~/.tgo-widget/config.json` after running `init`:

```json
{
  "server": "http://localhost:8000/api",
  "api_key": "pk_...",
  "visitor_id": "...",
  "platform_open_id": "...",
  "channel_id": "...",
  "channel_type": 251,
  "im_token": "...",
  "platform_id": "..."
}
```
