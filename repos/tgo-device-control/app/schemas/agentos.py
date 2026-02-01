"""AgentOS compatible API schemas.

This module defines Pydantic models for the custom AgentOS-compatible API
that works with agno's RemoteAgent while using McpAgent internally.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentRunEventType(str, Enum):
    """Event types for SSE streaming during agent execution."""

    # Connection events
    CONNECTED = "connected"

    # Execution lifecycle events
    RUN_STARTED = "run_started"
    ROUND_STARTED = "round_started"
    SCREENSHOT_TAKEN = "screenshot_taken"
    PLANNING_COMPLETE = "planning_complete"
    GROUNDING_COMPLETE = "grounding_complete"
    ACTION_EXECUTED = "action_executed"
    ROUND_COMPLETE = "round_complete"
    RUN_COMPLETE = "run_complete"

    # Content streaming (for compatibility with agno)
    CONTENT = "content"
    CONTENT_DELTA = "content_delta"

    # Error events
    ERROR = "error"


class ActionInfo(BaseModel):
    """Information about an action to be executed."""

    type: str = Field(..., description="Action type (click, type, scroll, etc.)")
    target: Optional[str] = Field(None, description="Target element description")
    x: Optional[int] = Field(None, description="X coordinate")
    y: Optional[int] = Field(None, description="Y coordinate")
    text: Optional[str] = Field(None, description="Text to type")
    keys: Optional[List[str]] = Field(None, description="Keys for hotkey")
    direction: Optional[str] = Field(None, description="Scroll direction")
    amount: Optional[int] = Field(None, description="Scroll amount")


class AgentRunEvent(BaseModel):
    """SSE event emitted during agent execution.

    Compatible with agno's RunOutputEvent format while providing
    additional computer use specific information.
    """

    event_type: AgentRunEventType = Field(..., description="Type of the event")
    run_id: str = Field(default_factory=lambda: str(uuid4()), description="Run ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp"
    )

    # Content fields (for agno compatibility)
    content: Optional[str] = Field(None, description="Text content for the event")
    content_delta: Optional[str] = Field(None, description="Incremental content update")

    # Computer Use specific fields
    round_number: Optional[int] = Field(None, description="Current round number")
    max_rounds: Optional[int] = Field(None, description="Maximum rounds allowed")

    # Screenshot data
    screenshot_b64: Optional[str] = Field(
        None, description="Base64 encoded screenshot (only in screenshot_taken event)"
    )

    # Planning data
    reasoning: Optional[str] = Field(None, description="Agent's reasoning")
    planned_action: Optional[ActionInfo] = Field(None, description="Planned action")
    is_task_complete: Optional[bool] = Field(
        None, description="Whether the task is complete"
    )

    # Grounding data
    target_element: Optional[str] = Field(
        None, description="Element being located"
    )
    grounded_coordinates: Optional[Dict[str, int]] = Field(
        None, description="Located coordinates {x, y}"
    )
    grounding_confidence: Optional[float] = Field(
        None, description="Confidence score for grounding"
    )

    # Action execution data
    executed_action: Optional[ActionInfo] = Field(
        None, description="Action that was executed"
    )
    action_success: Optional[bool] = Field(
        None, description="Whether the action succeeded"
    )
    action_message: Optional[str] = Field(
        None, description="Result message from action"
    )

    # Final result
    final_result: Optional[str] = Field(
        None, description="Final result when task completes"
    )

    # Error information
    error: Optional[str] = Field(None, description="Error message if any")
    error_code: Optional[str] = Field(None, description="Error code if any")

    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )

    def to_sse_format(self) -> str:
        """Format the event for SSE transmission.

        Returns:
            SSE formatted string with event type and JSON data.
        """
        import json

        # Create a dict excluding None values for cleaner output
        data = self.model_dump(exclude_none=True)
        # Convert datetime to ISO format string
        if "timestamp" in data:
            data["timestamp"] = data["timestamp"].isoformat()

        return f"data: {json.dumps(data)}\n\n"


class AgentRunRequest(BaseModel):
    """Request schema for running an agent.

    Compatible with agno's form-data format while supporting
    additional parameters for Computer Use.
    """

    message: str = Field(..., description="User message/task to execute")
    stream: bool = Field(default=True, description="Enable streaming response")

    # Optional identifiers
    user_id: Optional[str] = Field(None, description="User ID for the run")
    session_id: Optional[str] = Field(None, description="Session ID for context")

    # Computer Use specific
    device_id: Optional[str] = Field(
        None,
        description="Device ID to control. If not provided, extracted from message.",
    )
    max_rounds: Optional[int] = Field(
        None, description="Maximum rounds for agent loop"
    )

    # Additional parameters
    session_state: Optional[Dict[str, Any]] = Field(
        None, description="Session state dictionary"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )
    dependencies: Optional[Dict[str, Any]] = Field(
        None, description="Runtime dependencies"
    )

    # Auth
    auth_token: Optional[str] = Field(None, description="JWT token for authentication")


class ToolInfo(BaseModel):
    """Information about an available tool."""

    name: str = Field(..., description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    parameters: Optional[Dict[str, Any]] = Field(
        None, description="Tool parameter schema"
    )


class AgentConfig(BaseModel):
    """Agent configuration response.

    Compatible with agno's AgentResponse format.
    """

    id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    role: Optional[str] = Field(None, description="Agent role")
    model: Optional[str] = Field(None, description="Model being used")
    tools: Optional[List[ToolInfo]] = Field(None, description="Available tools")

    # Computer Use specific
    max_rounds: int = Field(default=20, description="Maximum rounds for agent loop")
    planning_model: Optional[str] = Field(None, description="Planning model ID")
    grounding_model: Optional[str] = Field(None, description="Grounding backend")

    # Capabilities
    supports_streaming: bool = Field(default=True)
    supports_vision: bool = Field(default=True)
    supports_computer_use: bool = Field(default=True)


class AgentRunResponse(BaseModel):
    """Non-streaming response for agent run.

    Used when stream=false is requested.
    """

    run_id: str = Field(..., description="Run ID")
    status: str = Field(..., description="Run status (completed, failed, etc.)")
    content: str = Field(..., description="Final response content")

    # Execution summary
    rounds_executed: int = Field(default=0, description="Number of rounds executed")
    actions_executed: int = Field(default=0, description="Number of actions executed")
    screenshots_taken: int = Field(default=0, description="Number of screenshots taken")

    # Result
    task_completed: bool = Field(default=False, description="Whether task was completed")
    final_result: Optional[str] = Field(None, description="Task completion result")
    error: Optional[str] = Field(None, description="Error if failed")

    # Timing
    started_at: datetime = Field(..., description="Run start time")
    completed_at: datetime = Field(..., description="Run completion time")
    duration_ms: int = Field(default=0, description="Total duration in milliseconds")


class AgentListResponse(BaseModel):
    """Response for listing available agents."""

    agents: List[AgentConfig] = Field(..., description="List of available agents")


class CancelRunRequest(BaseModel):
    """Request to cancel a running agent."""

    run_id: str = Field(..., description="Run ID to cancel")


class CancelRunResponse(BaseModel):
    """Response for cancel run request."""

    success: bool = Field(..., description="Whether cancellation was successful")
    message: Optional[str] = Field(None, description="Additional message")
