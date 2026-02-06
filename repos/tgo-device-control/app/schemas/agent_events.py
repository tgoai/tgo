"""Agent Event schemas for streaming execution status.

This module defines Pydantic models for events emitted during MCP Agent execution.
These events are used for real-time streaming of agent progress to clients.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentEventType(str, Enum):
    """Event types emitted during agent execution."""

    # Lifecycle events
    STARTED = "started"
    COMPLETED = "completed"
    ERROR = "error"

    # Tool events
    TOOLS_LOADED = "tools_loaded"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # Thinking/reasoning events
    THINKING = "thinking"

    # Progress events
    ITERATION_START = "iteration_start"
    ITERATION_END = "iteration_end"


class ToolCallInfo(BaseModel):
    """Information about a tool call."""

    name: str = Field(..., description="Tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolResultInfo(BaseModel):
    """Information about a tool result."""

    name: str = Field(..., description="Tool name")
    success: bool = Field(default=True, description="Whether the tool call succeeded")
    content: Optional[str] = Field(None, description="Text content from result")
    has_image: bool = Field(default=False, description="Whether result contains image")
    error: Optional[str] = Field(None, description="Error message if failed")


class AgentEvent(BaseModel):
    """Event emitted during agent execution.

    This model supports SSE streaming and provides detailed information
    about each step of the agent's execution.
    """

    event_type: AgentEventType = Field(..., description="Type of the event")
    run_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique run identifier",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp",
    )

    # Content
    content: Optional[str] = Field(None, description="Human-readable event content")

    # Tool information
    tool_call: Optional[ToolCallInfo] = Field(None, description="Tool call info")
    tool_result: Optional[ToolResultInfo] = Field(None, description="Tool result info")

    # Iteration tracking
    iteration: Optional[int] = Field(None, description="Current iteration number")
    max_iterations: Optional[int] = Field(None, description="Maximum iterations")

    # Completion info
    final_result: Optional[str] = Field(None, description="Final result when completed")
    success: bool = Field(default=True, description="Whether operation succeeded")

    # Error info
    error: Optional[str] = Field(None, description="Error message if any")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")

    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    def to_sse(self) -> str:
        """Format event for Server-Sent Events transmission.

        Returns:
            SSE formatted string with JSON data.
        """
        data = self.model_dump(exclude_none=True)
        # Convert datetime to ISO format
        if "timestamp" in data:
            data["timestamp"] = data["timestamp"].isoformat()
        return f"data: {json.dumps(data)}\n\n"

    @classmethod
    def started(
        cls,
        run_id: str,
        task: str,
        max_iterations: int,
        device_id: Optional[str] = None,
    ) -> "AgentEvent":
        """Create a STARTED event.

        Args:
            run_id: Unique run identifier.
            task: Task description.
            max_iterations: Maximum iterations allowed.
            device_id: Optional device identifier.

        Returns:
            AgentEvent for task start.
        """
        return cls(
            event_type=AgentEventType.STARTED,
            run_id=run_id,
            content=f"Starting task: {task}",
            max_iterations=max_iterations,
            metadata={"device_id": device_id} if device_id else None,
        )

    @classmethod
    def tools_loaded(
        cls,
        run_id: str,
        tool_count: int,
        tool_names: Optional[List[str]] = None,
    ) -> "AgentEvent":
        """Create a TOOLS_LOADED event.

        Args:
            run_id: Unique run identifier.
            tool_count: Number of tools loaded.
            tool_names: Optional list of tool names.

        Returns:
            AgentEvent for tools loaded.
        """
        return cls(
            event_type=AgentEventType.TOOLS_LOADED,
            run_id=run_id,
            content=f"Loaded {tool_count} tools from device",
            metadata={"tool_names": tool_names} if tool_names else None,
        )

    @classmethod
    def thinking(
        cls,
        run_id: str,
        iteration: int,
        max_iterations: int,
        content: Optional[str] = None,
    ) -> "AgentEvent":
        """Create a THINKING event.

        Args:
            run_id: Unique run identifier.
            iteration: Current iteration number.
            max_iterations: Maximum iterations.
            content: Optional thinking content.

        Returns:
            AgentEvent for thinking phase.
        """
        return cls(
            event_type=AgentEventType.THINKING,
            run_id=run_id,
            content=content or "Analyzing and deciding next action...",
            iteration=iteration,
            max_iterations=max_iterations,
        )

    @classmethod
    def create_tool_call(
        cls,
        run_id: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        iteration: int,
    ) -> "AgentEvent":
        """Create a TOOL_CALL event.

        Args:
            run_id: Unique run identifier.
            tool_name: Name of the tool being called.
            tool_args: Arguments for the tool.
            iteration: Current iteration number.

        Returns:
            AgentEvent for tool call.
        """
        return cls(
            event_type=AgentEventType.TOOL_CALL,
            run_id=run_id,
            content=f"Calling tool: {tool_name}",
            tool_call=ToolCallInfo(name=tool_name, arguments=tool_args),
            iteration=iteration,
        )

    @classmethod
    def create_tool_result(
        cls,
        run_id: str,
        tool_name: str,
        result: Dict[str, Any],
        iteration: int,
    ) -> "AgentEvent":
        """Create a TOOL_RESULT event.

        Args:
            run_id: Unique run identifier.
            tool_name: Name of the tool that was called.
            result: Result from the tool.
            iteration: Current iteration number.

        Returns:
            AgentEvent for tool result.
        """
        # Parse result
        is_error = result.get("isError", False) or "error" in result
        has_image = False
        text_content = None
        error_msg = None

        if is_error:
            content_list = result.get("content", [])
            for item in content_list:
                if item.get("type") == "text":
                    error_msg = item.get("text")
                    break
            if isinstance(result.get("error"), dict):
                error_msg = result["error"].get("message", error_msg)
            elif isinstance(result.get("error"), str):
                error_msg = result["error"]
        else:
            content_list = result.get("content", [])
            for item in content_list:
                if item.get("type") == "text":
                    text_content = item.get("text")
                elif item.get("type") == "image":
                    has_image = True

        return cls(
            event_type=AgentEventType.TOOL_RESULT,
            run_id=run_id,
            content=f"Tool {tool_name} {'failed' if is_error else 'completed'}",
            tool_result=ToolResultInfo(
                name=tool_name,
                success=not is_error,
                content=text_content,
                has_image=has_image,
                error=error_msg,
            ),
            iteration=iteration,
            success=not is_error,
        )

    @classmethod
    def completed(
        cls,
        run_id: str,
        final_result: str,
        iteration: int,
    ) -> "AgentEvent":
        """Create a COMPLETED event.

        Args:
            run_id: Unique run identifier.
            final_result: Final result message.
            iteration: Iteration when completed.

        Returns:
            AgentEvent for task completion.
        """
        return cls(
            event_type=AgentEventType.COMPLETED,
            run_id=run_id,
            content=final_result,
            final_result=final_result,
            iteration=iteration,
            success=True,
        )

    @classmethod
    def create_error(
        cls,
        run_id: str,
        error_message: str,
        error_code: Optional[str] = None,
        iteration: Optional[int] = None,
    ) -> "AgentEvent":
        """Create an ERROR event.

        Args:
            run_id: Unique run identifier.
            error_message: Error description.
            error_code: Optional error code.
            iteration: Optional iteration when error occurred.

        Returns:
            AgentEvent for error.
        """
        return cls(
            event_type=AgentEventType.ERROR,
            run_id=run_id,
            content=error_message,
            error=error_message,
            error_code=error_code,
            iteration=iteration,
            success=False,
        )


class AgentRunRequest(BaseModel):
    """Request schema for running the MCP agent."""

    task: str = Field(..., description="Task description to execute")
    device_id: str = Field(..., description="ID of the device to control")
    stream: bool = Field(default=True, description="Enable streaming response")

    # Model configuration (for tgo-ai service)
    provider_id: Optional[str] = Field(
        None,
        description="AI Provider ID for LLM calls via tgo-ai service",
    )
    model: Optional[str] = Field(
        None,
        description="LLM model to use (default from config)",
    )
    project_id: Optional[str] = Field(
        None,
        description="Project ID for authorization",
    )

    # Optional settings
    max_iterations: Optional[int] = Field(
        None,
        description="Maximum iterations (default from config)",
    )
    system_prompt: Optional[str] = Field(
        None,
        description="Custom system prompt to override default agent behavior",
    )

    # Auth
    user_id: Optional[str] = Field(None, description="User ID for the run")
    session_id: Optional[str] = Field(None, description="Session ID for context")


class AgentRunResponse(BaseModel):
    """Non-streaming response for agent run."""

    run_id: str = Field(..., description="Unique run identifier")
    status: str = Field(..., description="Run status (completed, failed, etc.)")
    result: str = Field(..., description="Final result or error message")

    # Execution stats
    iterations: int = Field(default=0, description="Number of iterations executed")
    tool_calls: int = Field(default=0, description="Number of tool calls made")

    # Timing
    started_at: datetime = Field(..., description="Run start time")
    completed_at: datetime = Field(..., description="Run completion time")
    duration_ms: int = Field(default=0, description="Total duration in milliseconds")

    # Result details
    success: bool = Field(default=True, description="Whether task completed successfully")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Error code if failed")
