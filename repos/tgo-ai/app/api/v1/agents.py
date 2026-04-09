"""Agent management API endpoints."""

import uuid
from typing import Optional, Union

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.core.logging import get_logger
from app.dependencies import (
    get_agent_service,
    get_pagination_params,
    get_supervisor_runtime_service,
)

logger = get_logger(__name__)
from app.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
    AgentWithDetails,
    ToggleEnabledRequest,
)
from app.schemas.base import PaginationMetadata
from app.api.responses import build_error_responses
from app.runtime.supervisor.application.service import SupervisorRuntimeService
from app.services.agent_service import AgentService

from app.schemas.agent_run import SupervisorRunRequest, SupervisorRunResponse




class CancelRunRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Optional reason for cancellation (for auditing/logs)")

router = APIRouter()


_STREAMING_EXAMPLE = (
    "event: connected\n"
    "data: {\"message\": \"Stream connected\", \"request_id\": \"req-123\", \"correlation_id\": \"corr-456\"}\n\n"
    "event: event\n"
    "data: {\"event_type\": \"workflow_started\", \"timestamp\": \"2024-05-01T12:00:00Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"info\", \"data\": {\"request_id\": \"req-123\", \"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"session_id\": \"sess-1\", \"message_length\": 128}, \"metadata\": {\"phase\": \"initialization\", \"agent_id\": \"agent-001\", \"session_id\": \"sess-1\"}}\n\n"
    "event: event\n"
    "data: {\"event_type\": \"agent_execution_started\", \"timestamp\": \"2024-05-01T12:00:01Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"info\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"question\": \"How do I fix this error?\"}, \"metadata\": {\"phase\": \"execution\", \"step\": 3}}\n\n"
    "event: event\n"
    "data: {\"event_type\": \"agent_content_chunk\", \"timestamp\": \"2024-05-01T12:00:02Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"info\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"content_chunk\": \"Investigating...\", \"chunk_index\": 0, \"is_final\": false}, \"metadata\": {\"phase\": \"agent_execution\", \"agent_id\": \"agent-001\"}}\n\n"
    "event: event\n"
    "data: {\"event_type\": \"agent_tool_call_started\", \"timestamp\": \"2024-05-01T12:00:03Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"info\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"tool_name\": \"search\", \"tool_call_id\": \"tc_01\", \"tool_input\": {\"query\": \"error logs\"}, \"status\": \"started\"}, \"metadata\": {\"phase\": \"agent_execution\", \"agent_id\": \"agent-001\", \"tool_name\": \"search\"}}\n\n"
    "event: event\n"
    "data: {\"event_type\": \"agent_tool_call_completed\", \"timestamp\": \"2024-05-01T12:00:04Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"success\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"tool_name\": \"search\", \"tool_call_id\": \"tc_01\", \"tool_input\": {\"query\": \"error logs\"}, \"tool_output\": \"3 results\", \"status\": \"completed\"}, \"metadata\": {\"phase\": \"agent_execution\", \"agent_id\": \"agent-001\", \"tool_name\": \"search\"}}\n\n"
    "event: event\n"
    "data: {\"event_type\": \"agent_response_complete\", \"timestamp\": \"2024-05-01T12:00:05Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"success\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"final_content\": \"Please restart the worker and retry.\", \"success\": true, \"total_chunks\": 1, \"tool_calls_count\": 1, \"response_length\": 35}, \"metadata\": {\"phase\": \"agent_execution\", \"agent_id\": \"agent-001\"}}\n\n"
    "event: event\n"
    "data: {\"event_type\": \"workflow_completed\", \"timestamp\": \"2024-05-01T12:00:08Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"success\", \"data\": {\"phase\": \"completed\", \"progress_percentage\": 100.0, \"current_step\": \"Workflow completed\", \"total_steps\": 4, \"completed_steps\": 4}, \"metadata\": {\"total_execution_time\": 8.0, \"agents_consulted\": 1}}\n\n"
    "event: disconnected\n"
    "data: {\"message\": \"Stream disconnected\"}\n\n"
)


_run_success_responses = {
    200: {
        "description": "Successful response. Returns JSON when `stream=false` and Server-Sent Events when `stream=true`.",
        "content": {
            "application/json": {
                "schema": {
                    "$ref": "#/components/schemas/SupervisorRunResponse",
                },
            },
            "text/event-stream": {
                "schema": {"type": "string", "description": "Server-Sent Events (SSE) stream. Event names: connected | event | error | disconnected. Domain events use 'event' with a StreamingEvent JSON payload."},
                "examples": {
                    "agent_execution_started": {
                        "summary": "Agent execution started (domain event)",
                        "value": "event: event\ndata: {\"event_type\": \"agent_execution_started\", \"timestamp\": \"2024-05-01T12:00:01Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"info\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"question\": \"How do I fix this error?\"}, \"metadata\": {\"phase\": \"execution\", \"step\": 3}}\n\n"
                    },
                    "agent_content_chunk": {
                        "summary": "Agent content chunk (domain event)",
                        "value": "event: event\ndata: {\"event_type\": \"agent_content_chunk\", \"timestamp\": \"2024-05-01T12:00:02Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"info\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"content_chunk\": \"Found 3 docs...\", \"chunk_index\": 0, \"is_final\": false}, \"metadata\": {\"phase\": \"agent_execution\", \"agent_id\": \"agent-001\"}}\n\n"
                    },
                    "agent_tool_call_started": {
                        "summary": "Agent tool call started (domain event)",
                        "value": "event: event\ndata: {\"event_type\": \"agent_tool_call_started\", \"timestamp\": \"2024-05-01T12:00:03Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"info\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"tool_name\": \"search\", \"tool_call_id\": \"tc_01\", \"tool_input\": {\"query\": \"...\"}, \"status\": \"started\"}, \"metadata\": {\"phase\": \"agent_execution\", \"agent_id\": \"agent-001\", \"tool_name\": \"search\"}}\n\n"
                    },
                    "agent_tool_call_completed": {
                        "summary": "Agent tool call completed (domain event)",
                        "value": "event: event\ndata: {\"event_type\": \"agent_tool_call_completed\", \"timestamp\": \"2024-05-01T12:00:04Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"success\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"tool_name\": \"search\", \"tool_call_id\": \"tc_01\", \"tool_input\": {\"query\": \"...\"}, \"tool_output\": \"3 results\", \"status\": \"completed\"}, \"metadata\": {\"phase\": \"agent_execution\", \"agent_id\": \"agent-001\", \"tool_name\": \"search\"}}\n\n"
                    },
                    "agent_response_complete": {
                        "summary": "Agent response complete (domain event)",
                        "value": "event: event\ndata: {\"event_type\": \"agent_response_complete\", \"timestamp\": \"2024-05-01T12:00:05Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"success\", \"data\": {\"agent_id\": \"agent-001\", \"agent_name\": \"Support Agent\", \"execution_id\": \"run-abc\", \"final_content\": \"Resolved output\", \"success\": true, \"total_chunks\": 1, \"tool_calls_count\": 1, \"response_length\": 15}, \"metadata\": {\"phase\": \"agent_execution\", \"agent_id\": \"agent-001\"}}\n\n"
                    },
                    "error_event": {
                        "summary": "SSE transport error",
                        "value": "event: error\ndata: {\"message\": \"Stream error occurred\", \"error\": \"TimeoutError\"}\n\n"
                    },
                    "domain_workflow_completed": {
                        "summary": "Workflow completed (domain event)",
                        "value": "event: event\ndata: {\"event_type\": \"workflow_completed\", \"timestamp\": \"2024-05-01T12:00:05Z\", \"correlation_id\": \"corr-456\", \"request_id\": \"req-123\", \"severity\": \"success\", \"data\": {\"phase\": \"completed\", \"progress_percentage\": 100.0, \"current_step\": \"Workflow completed\", \"total_steps\": 4, \"completed_steps\": 4}, \"metadata\": {\"total_execution_time\": 5.0, \"agents_consulted\": 1}}\n\n"
                    },
                    "full_sequence": {
                        "summary": "Full sequence example",
                        "value": _STREAMING_EXAMPLE
                    }
                },
            },
        },
    }
}


@router.post(
    "/run",
    response_model=SupervisorRunResponse,
    responses={
        **_run_success_responses,
        **build_error_responses(
            [400, 404, 429, 500],
            {
                404: "Agent resource not found",
                429: "Agent service rate limit exceeded",
                500: "Agent service unavailable",
            },
        ),
    },
)
async def run_supervisor_agent(
    payload: SupervisorRunRequest,
    request: Request,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    runtime_service: SupervisorRuntimeService = Depends(get_supervisor_runtime_service),
) -> Union[SupervisorRunResponse, StreamingResponse]:
    """Run the supervisor agent.

    Response content types:
    - application/json: Returned when `payload.stream=false`.
    - text/event-stream (SSE): Returned when `payload.stream=true`.

    Server-Sent Events (SSE):
    - Framing: Each SSE is formatted as `event: <type>` then `data: <json>` followed by a blank line.
    - SSE event names used by this endpoint:
      - connected: initial connection info
      - event: domain events encoded as a StreamingEvent JSON object (see structure below)
      - error: transport/stream errors
      - disconnected: stream closed
    - StreamingEvent JSON structure (payload of the 'event' SSE):
      {
        "event_type": "<EventType>",
        "timestamp": "RFC3339",
        "correlation_id": "string",
        "request_id": "string",
        "severity": "info|warning|error|success",
        "data": { ... event-specific fields ... },
        "metadata": { ... optional key/value metadata ... }
      }
    - Representative event_type values (see app/models/streaming.py for the full list):
      - workflow_started, workflow_completed, workflow_failed
      - agent_execution_started
      - agent_content_chunk, agent_tool_call_started, agent_tool_call_completed, agent_response_complete
    - Representative event data models (payloads in StreamingEvent.data):
      - WorkflowStartedData: request_id, agent_id, agent_name, session_id?, message_length
      - AgentExecutionData: agent_id, agent_name, execution_id, question, execution_time?, success?, error?, response_length?
      - AgentContentChunkData: agent_id, agent_name, execution_id, content_chunk, chunk_index, is_final
      - AgentToolCallData: agent_id, agent_name, execution_id, tool_name, tool_call_id?, tool_input?, tool_output?, status, error?
      - AgentResponseCompleteData: agent_id, agent_name, execution_id, final_content, success, total_chunks, tool_calls_count, response_length

    Error handling:
    - Operational errors during streaming are emitted as an `error` event and the stream terminates.
    - If validation errors occur before streaming starts, the response is a non-200 JSON error with an appropriate HTTP status (e.g., 400/404/429/500).

    Typical event sequence:
    1) connected (informational)
    2) event(workflow_started)
    3) zero or more domain events, including:
       - agent_execution_started
       - agent_content_chunk
       - agent_tool_call_started / agent_tool_call_completed
       - agent_response_complete

    4) event(workflow_completed) on success OR event(workflow_failed) on failure
    5) disconnected (stream ends)

    Error handling:
    - Operational/transport errors during streaming may be emitted as an `error` SSE and the stream terminates.
    - Domain failures are emitted as an `event` SSE whose payload has `event_type: workflow_failed` (severity: error), then the stream closes.

    Client guidance:
    - JavaScript: use EventSource and listen to 'event' to handle domain events; parse `event_type` from JSON.
      const es = new EventSource(url);
      es.addEventListener('event', (e) => {
        const evt = JSON.parse(e.data);
        switch (evt.event_type) {
          case 'agent_execution_started': /* initialize single-agent UI */ break;
          case 'agent_content_chunk': /* handle text chunk */ break;
          case 'agent_tool_call_started': /* ... */ break;
          case 'agent_tool_call_completed': /* ... */ break;
          case 'agent_response_complete': /* finalize agent output */ break;
          case 'workflow_completed': es.close(); break;
          case 'workflow_failed': es.close(); break;
          default: /* optionally log unknown types */ break;
        }
      });
      es.addEventListener('connected', () => { /* optional: connection ack */ });
      es.addEventListener('error', () => { /* close or retry if desired */ });
      es.addEventListener('disconnected', () => { /* stream closed */ });
    - Python: use an SSE client (e.g., sseclient or httpx stream) and parse `event:` and `data:` lines, reading `event_type` from JSON.

    Notes:
    - Completion can be detected via the 'disconnected' SSE or by seeing domain events `workflow_completed`/`workflow_failed`.
    - For reconnection, carry over `correlation_id`/`request_id` if supported by your integration.
    """

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # Build headers for downstream services (no authentication)
    extra_headers = {
        "X-Project-ID": str(project_id),
    }



    if payload.rag_url is None:
        payload = payload.model_copy(update={"rag_url": settings.rag_service_url})

    if payload.mcp_url is None:
        payload = payload.model_copy(update={"mcp_url": settings.mcp_service_url})

    if payload.stream:
        sse_response = await runtime_service.stream(
            payload,
            project_id,
            extra_headers={**extra_headers, "X-Request-ID": request_id},
            http_request=request,
        )
        return sse_response

    response = await runtime_service.run(
        payload,
        project_id,
        extra_headers={**extra_headers, "X-Request-ID": request_id},
    )
    return response


@router.post(
    "/run/{run_id}/cancel",
    status_code=status.HTTP_202_ACCEPTED,
    responses=build_error_responses([500]),
)
async def cancel_supervisor_run(
    run_id: str,
    payload: Optional[CancelRunRequest] = None,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    runtime_service: SupervisorRuntimeService = Depends(get_supervisor_runtime_service),
) -> dict:
    """Cancel a running supervisor agent execution by run_id.

    Always returns 202 Accepted. Body indicates whether a cancel signal was issued.
    """
    reason = payload.reason if payload else None
    cancelled = await runtime_service.cancel(run_id, project_id, reason=reason)
    return {"run_id": run_id, "cancelled": cancelled, "reason": reason}



@router.get(
    "/exists",
    response_model=dict,
    responses=build_error_responses([]),
    summary="Check if agents exist for project",
)
async def check_agents_exist(
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> dict:
    """
    Check if any agents exist for the specified project.

    Returns a simple boolean response indicating whether the project has any agents.
    This is useful for quick existence checks without fetching full agent data.
    """
    agents, total_count = await agent_service.list_agents(
        project_id=project_id,
        limit=1,
        offset=0,
    )
    return {"exists": total_count > 0, "count": total_count}


@router.delete(
    "/sessions/{session_id}/memory",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear session memory",
)
async def clear_session_memory(
    session_id: str,
    project_id: uuid.UUID = Query(...),
    user_id: Optional[str] = Query(default=None, description="Optional user ID to clear personal memories"),
    agent_service: AgentService = Depends(get_agent_service),
) -> None:
    """Clear all memory and session history for a specific session.
    
    This deletes records from agno memory and session tables in the 'ai' schema.
    If user_id is provided, it also clears personal memories for that user from agno_memories.
    """
    await agent_service.clear_session_memory(
        session_id=session_id,
        project_id=project_id,
        user_id=user_id
    )
    logger.info(f"Cleared session memory for {session_id} (project: {project_id}, user: {user_id})")


@router.get(
    "",
    response_model=AgentListResponse,
    responses=build_error_responses([]),
)
async def list_agents(
    model: Optional[str] = Query(default=None, description="Filter by model (provider:model_name, e.g., openai:gpt-4)"),
    is_default: Optional[bool] = Query(default=None, description="Filter by default agent status"),
    pagination: tuple[int, int] = Depends(get_pagination_params),
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentListResponse:
    """
    Retrieve all AI agents for the authenticated project with filtering and pagination.

    Returns detailed agent information including associated tools and collections.

    **Filtering Options:**
    - Filter by LLM model (provider:model_name format)
    - Filter by default agent status
    - Pagination with configurable limits

    **Response Details:**
    - Each agent includes basic information (id, name, model, etc.)
    - Associated tools with their configurations and permissions
    - Associated collections with their metadata
    **Project Scope:**
    - Only agents belonging to the specified project_id are returned
    """
    limit, offset = pagination
    agents, total_count = await agent_service.list_agents(
        project_id=project_id,
        model=model,
        is_default=is_default,
        limit=limit,
        offset=offset,
    )

    return AgentListResponse(
        data=[AgentWithDetails.model_validate(agent) for agent in agents],
        pagination=PaginationMetadata(
            total=total_count,
            limit=limit,
            offset=offset,
            has_next=offset + limit < total_count,
            has_prev=offset > 0,
        ),
    )


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    responses=build_error_responses(
        [400, 404, 409],
        {404: "Referenced team or collection not found", 409: "Agent name conflict"},
    ),
)
async def create_agent(
    agent_data: AgentCreate,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    """
    Create a new AI agent for the authenticated project.

    **Agent Configuration:**
    - Specify LLM model in "provider:model_name" format
    - Configure system instruction and behavior
    - Bind tools with specific permissions and configurations
    - Set default agent status (only one per project)

    **Tool Integration:**
    - Tools specified in "tool_provider:tool_name" format
    - Configure permissions and tool-specific settings
    - Enable/disable tools individually

    **Project Scope:**
    - Project is provided explicitly via the project_id query parameter
    - Cross-service consistency is maintained
    """
    agent = await agent_service.create_agent(project_id, agent_data)
    return AgentResponse.model_validate(agent)


@router.get(
    "/{agent_id}",
    response_model=AgentWithDetails,
    responses=build_error_responses([404], {404: "Agent not found"}),
)
async def get_agent(
    agent_id: uuid.UUID,
    include_tools: bool = Query(default=True, description="Include tool bindings in the response"),
    include_collections: bool = Query(default=False, description="Include collection bindings in the response"),
    include_workflows: bool = Query(default=False, description="Include workflow bindings in the response"),
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentWithDetails:
    """
    Retrieve detailed information about a specific AI agent including
    tool bindings and collection access if requested.
    """
    agent = await agent_service.get_agent(project_id, agent_id)
    return AgentWithDetails.model_validate(agent)


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    responses=build_error_responses(
        [400, 404, 409],
        {404: "Agent, team, or collection not found", 409: "Agent name conflict"},
    ),
)
async def update_agent(
    agent_id: uuid.UUID,
    agent_data: AgentUpdate,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    """
    Update AI agent configuration, tools, or settings.

    **Update Capabilities:**
    - Modify agent name, instruction, and model
    - Reconfigure tool bindings
    - Change default agent status
    - Update agent-specific configuration
    """
    agent = await agent_service.update_agent(project_id, agent_id, agent_data)
    return AgentResponse.model_validate(agent)


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=build_error_responses([404], {404: "Agent not found"}),
)
async def delete_agent(
    agent_id: uuid.UUID,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> None:
    """
    Soft delete an AI agent. The agent will be marked as deleted but
    preserved for audit purposes.
    """
    await agent_service.delete_agent(project_id, agent_id)


@router.patch(
    "/{agent_id}/tools/{tool_id}/enabled",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=build_error_responses([400, 404], {404: "Agent or tool binding not found"}),
)
async def set_agent_tool_enabled(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    payload: ToggleEnabledRequest,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> None:
    """Enable or disable a specific tool binding for an agent."""
    await agent_service.set_tool_enabled(project_id, agent_id, tool_id, payload.enabled)


@router.patch(
    "/{agent_id}/collections/{collection_id}/enabled",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=build_error_responses([400, 404], {404: "Agent or collection binding not found"}),
)
async def set_agent_collection_enabled(
    agent_id: uuid.UUID,
    collection_id: str,
    payload: ToggleEnabledRequest,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> None:
    """Enable or disable a specific collection binding for an agent."""
    await agent_service.set_collection_enabled(project_id, agent_id, collection_id, payload.enabled)


@router.patch(
    "/{agent_id}/workflows/{workflow_id}/enabled",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=build_error_responses([400, 404], {404: "Agent or workflow binding not found"}),
)
async def set_agent_workflow_enabled(
    agent_id: uuid.UUID,
    workflow_id: str,
    payload: ToggleEnabledRequest,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    agent_service: AgentService = Depends(get_agent_service),
) -> None:
    """Enable or disable a specific workflow binding for an agent."""
    await agent_service.set_workflow_enabled(project_id, agent_id, workflow_id, payload.enabled)
