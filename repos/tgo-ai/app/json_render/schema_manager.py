"""json-render schema manager for TGO AI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

_MODULE_DIR = Path(__file__).resolve().parent
_SCHEMA_PATH = _MODULE_DIR / "schema" / "spec_stream_line.json"
_EXAMPLES_DIR = _MODULE_DIR / "examples"

JSON_RENDER_SPEC_FENCE_OPEN = "```spec"
JSON_RENDER_SPEC_FENCE_CLOSE = "```"


class JsonRenderSchemaManager:
    """Manages json-render schema loading and system prompt generation."""

    def __init__(
        self,
        *,
        schema_path: Optional[Path] = None,
        examples_dir: Optional[Path] = None,
    ) -> None:
        self._schema_path = schema_path or _SCHEMA_PATH
        self._examples_dir = examples_dir or _EXAMPLES_DIR
        self._schema: Optional[dict] = None
        self._examples: Optional[str] = None
        self._load()

    def _load(self) -> None:
        if self._schema_path.exists():
            self._schema = json.loads(self._schema_path.read_text(encoding="utf-8"))
            logger.info("json-render patch schema loaded", path=str(self._schema_path))
        else:
            logger.warning("json-render patch schema not found", path=str(self._schema_path))

        if self._examples_dir.exists():
            parts: List[str] = []
            for p in sorted(self._examples_dir.glob("*.jsonl")):
                name = p.stem
                content = p.read_text(encoding="utf-8").strip()
                parts.append(f"### {name}\n```text\n{content}\n```")
            self._examples = "\n\n".join(parts) if parts else None
            logger.info("json-render examples loaded", count=len(parts))

    @property
    def schema_json(self) -> Optional[str]:
        if self._schema is None:
            return None
        return json.dumps(self._schema, indent=2, ensure_ascii=False)

    def generate_system_prompt(
        self,
        *,
        role_description: str = "",
        workflow_description: str = "",
        ui_description: str = "",
        include_schema: bool = True,
        include_examples: bool = True,
    ) -> str:
        """Assemble the json-render instruction block for the LLM prompt."""
        parts: List[str] = []
        parts.append(_JSON_RENDER_PROTOCOL_INSTRUCTIONS)

        if role_description:
            parts.append(f"## Role\n{role_description}")

        if workflow_description:
            parts.append(f"## Workflow\n{workflow_description}")

        if ui_description:
            parts.append(f"## UI Guidelines\n{ui_description}")

        if include_schema and self._schema is not None:
            parts.append(
                "## json-render Patch Schema\n"
                "Each JSONL patch line MUST validate against this schema.\n"
                f"```json\n{self.schema_json}\n```"
            )

        if include_examples and self._examples:
            parts.append(f"## json-render Examples\n{self._examples}")

        return "\n\n".join(parts)


_JSON_RENDER_PROTOCOL_INSTRUCTIONS = f"""\
## json-render Response Protocol

When generating rich UI you MUST follow these rules:

1. First write conversational text.
2. Then output JSONL SpecStream patch lines inside a fenced block:
   - opening fence: {JSON_RENDER_SPEC_FENCE_OPEN}
   - closing fence: {JSON_RENDER_SPEC_FENCE_CLOSE}
3. Inside the fence, each line MUST be a single RFC 6902 patch object.
4. Patches MUST build a **complete, self-contained** json-render spec. Each message's spec is rendered independently — there is NO cross-message state. You MUST always include:
   - `root`: string (REQUIRED — the spec will not render without it)
   - `elements`: object map of element definitions
   - optional `state`: object
   **NEVER emit incremental patches** that assume a previous message's spec still exists. Always output the full spec.
5. Each element MUST contain:
   - `type`: component name
   - `props`: object
   - optional `children`: string[]
   - optional `on`: event-action bindings
6. Use RFC 6902 operations: `add`, `replace`, `remove`, `move`, `copy`, `test`.
7. For interactive controls (button/form), bind events through `on` with action names and params.
8. Prefer structured components over plain text dumps:
   - key/value rows: `KV` or `PriceRow`
   - grouped blocks: `Section`
   - status and tags: `Badge`
   - action area: `ButtonGroup`
9. For order/invoice scenarios, strongly prefer this composition:
   - root `Card` with `variant: "order"`
   - header row with order id + status `Badge`
   - `Section` blocks for shipping, items, and payment
   - each line item uses `OrderItem`
   - totals use `PriceRow`; payable/total amount should set `emphasis=true`
   - action buttons are grouped in `ButtonGroup`
10. Available component types include:
   `Card`, `Column`, `Row`, `Text`, `Divider`, `Image`, `Button`, `ButtonGroup`,
   `Section`, `KV`, `PriceRow`, `Badge`, `OrderItem`,
   `Input`/`TextField`, `Checkbox`/`CheckBox`, `DateTimeInput`, `MultipleChoice`.
11. If you cannot produce valid SpecStream patches, return plain text only and DO NOT emit a spec fence.
12. For form scenarios:
   - Define initial form values in `state`: `"state": {{ "form": {{ "name": "", "phone": "" }} }}`
   - Bind input values with `{{ "$bindState": "/form/fieldName" }}` on the `value` prop
   - **Selection/toggle/filter buttons MUST use the built-in `setState` action** to update local state, e.g.:
     `"on": {{ "press": {{ "action": "setState", "params": {{ "statePath": "/form/date", "value": "today" }} }} }}`
   - Only the final submit/search/confirm button should use a custom action name, e.g.:
     `"on": {{ "press": {{ "action": "searchTrains" }} }}`
   - User's form input values are automatically collected and sent with the submit action
13. Built-in actions (setState, pushState, removeState, validateForm) are handled client-side.
    Do NOT use these as business action names.
14. Conditional / dynamic prop values — use the `$cond`/`$then`/`$else` expression:
   `{{ "$cond": {{ "$state": "/form/trainType", "eq": "G" }}, "$then": "primary", "$else": "secondary" }}`
   Condition operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`; add `"not": true` to negate.
   Read state: `{{ "$state": "/path" }}` in conditions, `{{ "$bindState": "/path" }}` for two-way binding on Input value.
   **NEVER use `$if` or `$eq` as expression keys** — they are NOT supported.
   Full example for a toggle-style filter button:
   ```
   {{ "type": "Button", "props": {{ "label": "高铁", "variant": {{ "$cond": {{ "$state": "/form/trainType", "eq": "G" }}, "$then": "primary", "$else": "secondary" }} }}, "on": {{ "press": {{ "action": "setState", "params": {{ "statePath": "/form/trainType", "value": "G" }} }} }} }}
   ```
15. Component prop conventions — all form components bind via the `value` prop:
   - `Input`/`TextField`: `{{ "value": {{ "$bindState": "/form/field" }} }}`
   - `Checkbox`/`CheckBox`: `{{ "value": {{ "$bindState": "/form/flag" }} }}` (boolean)
   - `DateTimeInput`: `{{ "value": {{ "$bindState": "/form/date" }} }}`
   - `MultipleChoice`: single-select dropdown. Use `value` prop (NOT `selectedValues` or `selectedValue`).
     State must be a string, NOT an array. Example:
     `{{ "type": "MultipleChoice", "props": {{ "label": "类型", "options": [...], "value": {{ "$bindState": "/form/type" }} }} }}`
"""
