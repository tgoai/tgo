from __future__ import annotations

import importlib.util

import app.dependencies as dependencies
import app.models as models
import app.schemas as schemas
import app.services as services
from app.models.project import Project


def test_openapi_excludes_team_routes_tags_and_examples(client) -> None:
    schema = client.get("/openapi.json").json()

    assert all(not path.startswith("/api/v1/teams") for path in schema["paths"])
    assert all(tag["name"] != "Teams" for tag in schema.get("tags", []))

    error_detail = schema["components"]["schemas"]["ErrorDetail"]
    message_examples = " ".join(error_detail["properties"]["message"]["examples"]).lower()
    details_examples = str(error_detail["properties"]["details"]["examples"])

    assert "team" not in message_examples
    assert "team_id" not in details_examples


def test_team_modules_are_removed_from_public_exports() -> None:
    assert importlib.util.find_spec("app.api.v1.teams") is None
    assert importlib.util.find_spec("app.services.team_service") is None
    assert importlib.util.find_spec("app.models.team") is None
    assert importlib.util.find_spec("app.schemas.team") is None

    assert not hasattr(dependencies, "get_team_service")
    assert not hasattr(models, "Team")
    assert not hasattr(services, "TeamService")
    assert not hasattr(schemas, "TeamCreate")


def test_project_model_is_agent_only() -> None:
    assert "teams" not in Project.__mapper__.relationships.keys()
