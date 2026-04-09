from __future__ import annotations

from uuid import uuid4

from app.models.agent import Agent
from migrations.versions.j2k3l4m5n6o7_backfill_agent_runtime_fields import (
    build_agent_runtime_backfill,
)


def test_build_agent_runtime_backfill_prefers_agent_fields_and_merges_team_defaults() -> None:
    provider_id = uuid4()

    updates = build_agent_runtime_backfill(
        {
            "model": "openai:gpt-4o-mini",
            "instruction": None,
            "llm_provider_id": None,
            "config": {
                "memory": {"window": 4},
                "expected_output": None,
            },
        },
        {
            "model": "anthropic:claude-3-5-sonnet",
            "instruction": "Team instruction",
            "expected_output": "Respond in JSON",
            "session_id": "team-session",
            "llm_provider_id": provider_id,
            "config": {
                "memory": {"enabled": True, "window": 12},
                "temperature": 0.2,
            },
        },
    )

    assert updates == {
        "model": "openai:gpt-4o-mini",
        "instruction": "Team instruction",
        "llm_provider_id": provider_id,
        "config": {
            "memory": {"enabled": True, "window": 4},
            "temperature": 0.2,
            "expected_output": None,
        },
    }


def test_build_agent_runtime_backfill_ignores_missing_team_values() -> None:
    updates = build_agent_runtime_backfill(
        {
            "model": "openai:gpt-4o",
            "instruction": "Agent instruction",
            "llm_provider_id": None,
            "config": {"temperature": 0.4},
        },
        None,
    )

    assert updates == {
        "model": "openai:gpt-4o",
        "instruction": "Agent instruction",
        "llm_provider_id": None,
        "config": {"temperature": 0.4},
    }


def test_agent_model_has_partial_unique_index_for_active_project_defaults() -> None:
    index = next(
        candidate
        for candidate in Agent.__table__.indexes
        if candidate.name == "uq_ai_agents_default_per_project_active"
    )

    assert index.unique is True
    assert "deleted_at IS NULL" in str(index.dialect_options["postgresql"]["where"])
