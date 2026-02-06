"""Seed script: Register tgo-device-control as an MCP tool in the ai_tools table.

Usage:
    python -m scripts.seed_device_control_tool --project-id <UUID>

This creates a LOCAL MCP tool record pointing to the tgo-device-control
MCP Streamable HTTP endpoint.  The endpoint uses a ``{device_id}`` template
variable that is replaced at runtime with the target device's UUID.

The tool must then be associated with an Agent via the
``ai_agent_tool_associations`` table (through the admin UI or API).
"""

import argparse
import uuid
import sys

import sqlalchemy as sa

# ------------------------------------------------------------------ #
#  Configuration – adjust to match your environment                    #
# ------------------------------------------------------------------ #

TABLE_NAME = "ai_tools"
TOOL_NAME = "device-control"
TOOL_TITLE_ZH = "设备控制"
TOOL_TITLE_EN = "Device Control"
TOOL_DESCRIPTION = (
    "MCP transparent proxy for remote device control. "
    "Dynamically exposes the target device's tools (e.g. screenshot, "
    "click, type, scroll) via the MCP protocol. The {device_id} in "
    "the endpoint URL is replaced at runtime with the target device ID."
)

# Docker internal network address; adjust host/port as needed
DEVICE_CONTROL_ENDPOINT = "http://tgo-device-control:8085/mcp/{device_id}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-id",
        required=True,
        type=str,
        help="Project UUID to register the tool under",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL connection URL (default: read from AI service .env)",
    )
    parser.add_argument(
        "--endpoint",
        default=DEVICE_CONTROL_ENDPOINT,
        help=f"MCP endpoint URL template (default: {DEVICE_CONTROL_ENDPOINT})",
    )
    args = parser.parse_args()

    # Resolve database URL
    db_url = args.database_url
    if not db_url:
        try:
            from app.config import settings  # type: ignore[import-untyped]
            db_url = str(settings.DATABASE_URL)
        except Exception:
            print(
                "ERROR: Could not determine database URL. "
                "Pass --database-url or run from the tgo-ai directory.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Ensure sync driver
    if "asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

    engine = sa.create_engine(db_url)

    tool_id = uuid.uuid4()
    project_id = uuid.UUID(args.project_id)

    insert_sql = sa.text(f"""
        INSERT INTO {TABLE_NAME} (
            id, project_id, name, title_zh, title_en, description,
            tool_type, transport_type, endpoint,
            tool_source_type, config,
            created_at, updated_at
        ) VALUES (
            :id, :project_id, :name, :title_zh, :title_en, :description,
            'MCP', 'http', :endpoint,
            'LOCAL', '{{}}'::jsonb,
            NOW(), NOW()
        )
        ON CONFLICT DO NOTHING
    """)

    with engine.begin() as conn:
        conn.execute(
            insert_sql,
            {
                "id": tool_id,
                "project_id": project_id,
                "name": TOOL_NAME,
                "title_zh": TOOL_TITLE_ZH,
                "title_en": TOOL_TITLE_EN,
                "description": TOOL_DESCRIPTION,
                "endpoint": args.endpoint,
            },
        )

    print(f"Tool registered successfully:")
    print(f"  ID:         {tool_id}")
    print(f"  Project:    {project_id}")
    print(f"  Name:       {TOOL_NAME}")
    print(f"  Endpoint:   {args.endpoint}")
    print(f"  Source:     LOCAL")
    print(f"  Transport:  http (MCP Streamable HTTP)")
    print()
    print(
        "Next step: Associate this tool with an Agent via the admin UI "
        "or the ai_agent_tool_associations table."
    )


if __name__ == "__main__":
    main()
