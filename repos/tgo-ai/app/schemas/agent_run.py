"""Schemas for single-agent runtime execution requests and responses."""

from __future__ import annotations

import uuid
from typing import List, Optional

from pydantic import ConfigDict, Field

from app.schemas.base import BaseSchema


class SupervisorRunRequest(BaseSchema):
    """Request payload for the single-agent `/agents/run` endpoint."""

    model_config = ConfigDict(extra="forbid")

    agent_id: Optional[str] = Field(
        default=None,
        description="UUID of the agent to execute. If omitted, the project default agent is used.",
    )
    message: str = Field(
        description="User message to be processed by the agent",
        min_length=1,
        max_length=10_000,
    )
    system_message: Optional[str] = Field(
        default=None,
        description="Optional system message appended after the stored agent instruction for this run",
    )
    expected_output: Optional[str] = Field(
        default=None,
        description="Optional expected output format override for this run",
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Session ID for conversation tracking",
    )
    user_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="User ID for authentication and token management",
    )
    stream: bool = Field(
        default=False,
        description="Enable streaming response with real-time events",
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout for agent execution in seconds",
    )
    mcp_url: Optional[str] = Field(
        default=None,
        description="URL of the MCP server for tool integration",
    )
    rag_url: Optional[str] = Field(
        default=None,
        description="URL of the RAG server for retrieval-augmented generation",
    )
    enable_memory: bool = Field(
        default=False,
        description="Enable conversational memory for the executing agent",
    )


class AgentExecutionResult(BaseSchema):
    """Result from a single agent execution."""

    agent_id: uuid.UUID = Field(description="UUID of the executed agent")
    agent_name: str = Field(description="Name of the executed agent")
    question: str = Field(description="Question asked to the agent")
    content: str = Field(description="Agent response content")
    tools_used: Optional[List[str]] = Field(
        default=None,
        description="List of tools used by the agent",
    )
    execution_time: float = Field(
        description="Execution time in seconds",
        ge=0,
    )
    success: bool = Field(
        default=True,
        description="Whether execution was successful",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed",
    )

    model_config = ConfigDict(extra="allow")


class AgentRunMetadata(BaseSchema):
    """Metadata about a single-agent execution."""

    agent_id: uuid.UUID = Field(description="Executing agent ID")
    agent_name: str = Field(description="Executing agent name")
    total_execution_time: float = Field(
        description="Total execution time in seconds",
        ge=0,
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Conversation session ID for this run",
    )

    model_config = ConfigDict(extra="allow")


SupervisorMetadata = AgentRunMetadata


class SupervisorRunResponse(BaseSchema):
    """Non-streaming response payload from `/agents/run`."""

    success: bool = Field(
        default=True,
        description="Whether the request was successful",
    )
    message: str = Field(description="Human-readable status message")
    result: Optional[AgentExecutionResult] = Field(
        default=None,
        description="Result from the executed agent",
    )
    content: str = Field(description="Final response content")
    metadata: Optional[AgentRunMetadata] = Field(
        default=None,
        description="Metadata about the execution",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if success is false",
    )

    model_config = ConfigDict(extra="allow")
