"""Streaming response models for the single-agent supervisor runtime."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types emitted by the single-agent supervisor runtime."""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    AGENT_EXECUTION_STARTED = "agent_execution_started"
    AGENT_CONTENT_CHUNK = "agent_content_chunk"
    AGENT_TOOL_CALL_STARTED = "agent_tool_call_started"
    AGENT_TOOL_CALL_COMPLETED = "agent_tool_call_completed"
    AGENT_RESPONSE_COMPLETE = "agent_response_complete"
    PROGRESS_UPDATE = "progress_update"
    ERROR_EVENT = "error_event"
    JSON_RENDER_UPDATE = "json_render_update"


class EventSeverity(str, Enum):
    """Event severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class BaseEventData(BaseModel):
    """Base class for all event payloads."""


class WorkflowStartedData(BaseEventData):
    """Data for workflow started events."""

    request_id: str
    agent_id: str
    agent_name: str
    session_id: Optional[str] = None
    message_length: int


class ProgressUpdateData(BaseEventData):
    """Data for workflow progress updates."""

    phase: str
    progress_percentage: float
    current_step: str
    total_steps: int
    completed_steps: int
    estimated_remaining_time: Optional[float] = None


class ErrorEventData(BaseEventData):
    """Data for workflow failure events."""

    error_type: str
    error_message: str
    component: str
    agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    stack_trace: Optional[str] = None


class AgentExecutionData(BaseEventData):
    """Data for direct agent execution lifecycle events."""

    agent_id: str
    agent_name: str
    execution_id: str
    question: str


class AgentContentChunkData(BaseEventData):
    """Data for streamed agent content chunks."""

    agent_id: str
    agent_name: str
    execution_id: str
    content_chunk: str
    chunk_index: int
    is_final: bool = False
    agent_role: Optional[str] = None


class AgentToolCallData(BaseEventData):
    """Data for streamed agent tool call events."""

    agent_id: str
    agent_name: str
    execution_id: str
    tool_name: str
    tool_call_id: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    status: str
    error: Optional[str] = None


class AgentResponseCompleteData(BaseEventData):
    """Data for final streamed agent responses."""

    agent_id: str
    agent_name: str
    execution_id: str
    final_content: str
    success: bool
    total_chunks: int
    tool_calls_count: int = 0
    response_length: int


class JsonRenderUpdateData(BaseEventData):
    """Data for json-render patch updates."""

    patches: List[Dict[str, Any]] = Field(
        ..., description="Array of RFC 6902 JSON Patch lines for json-render SpecStream"
    )
    text_content: Optional[str] = Field(
        default=None,
        description="Optional conversational text emitted before the json-render delimiter",
    )


class StreamingEvent(BaseModel):
    """A single streaming event emitted during one run."""

    event_type: EventType = Field(..., description="Type of the event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    correlation_id: str = Field(..., description="Correlation ID for tracking related events")
    request_id: str = Field(..., description="Request ID for the run")
    severity: EventSeverity = Field(default=EventSeverity.INFO, description="Event severity level")
    data: Union[
        WorkflowStartedData,
        ProgressUpdateData,
        ErrorEventData,
        AgentExecutionData,
        AgentContentChunkData,
        AgentToolCallData,
        AgentResponseCompleteData,
        JsonRenderUpdateData,
        BaseEventData,
    ] = Field(..., description="Event-specific payload")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {
            datetime: lambda value: value.isoformat(),
            UUID: lambda value: str(value),
        }
