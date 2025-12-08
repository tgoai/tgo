"""OpenAI-compatible Chat Completions API schemas.

These schemas are designed to be fully compatible with the OpenAI Chat Completions API,
with the addition of provider_id for selecting LLM provider credentials.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# =============================================================================
# Request Models
# =============================================================================


class FunctionCall(BaseModel):
    """Function call in a message."""

    name: str = Field(..., description="The name of the function to call")
    arguments: str = Field(..., description="JSON string of function arguments")


class ToolCall(BaseModel):
    """Tool call in a message."""

    id: str = Field(..., description="The ID of the tool call")
    type: Literal["function"] = Field(default="function", description="The type of tool call")
    function: FunctionCall = Field(..., description="The function call details")


class ChatMessage(BaseModel):
    """A message in the chat conversation."""

    role: Literal["system", "user", "assistant", "tool"] = Field(
        ..., description="The role of the message author"
    )
    content: Optional[str] = Field(
        default=None, description="The content of the message"
    )
    name: Optional[str] = Field(
        default=None, description="The name of the author (for user/assistant)"
    )
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None, description="Tool calls made by the assistant"
    )
    tool_call_id: Optional[str] = Field(
        default=None, description="The ID of the tool call this message is responding to"
    )


class FunctionDefinition(BaseModel):
    """Definition of a function that can be called."""

    name: str = Field(..., description="The name of the function")
    description: Optional[str] = Field(
        default=None, description="A description of what the function does"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON Schema for the function parameters"
    )


class ToolDefinition(BaseModel):
    """Definition of a tool that can be used."""

    type: Literal["function"] = Field(default="function", description="The type of tool")
    function: FunctionDefinition = Field(..., description="The function definition")


class ResponseFormat(BaseModel):
    """Response format specification."""

    type: Literal["text", "json_object"] = Field(
        default="text", description="The format of the response"
    )


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request with provider_id extension.

    This request schema is fully compatible with OpenAI's Chat Completions API,
    with the addition of provider_id for selecting LLM provider credentials.
    """

    # TGO-AI specific: provider credentials lookup
    provider_id: uuid.UUID = Field(
        ...,
        description="UUID of the LLM provider to use (from ai_llm_providers table)",
    )

    # Standard OpenAI parameters
    model: str = Field(
        ...,
        description="Model identifier (e.g., 'gpt-4', 'claude-3-opus', 'gemini-pro')",
    )
    messages: List[ChatMessage] = Field(
        ...,
        description="A list of messages comprising the conversation",
        min_length=1,
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream partial message deltas",
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0,
        le=2,
        description="Sampling temperature (0-2)",
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Nucleus sampling parameter",
    )
    n: Optional[int] = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of completions to generate",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of tokens to generate",
    )
    stop: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Stop sequences",
    )
    presence_penalty: Optional[float] = Field(
        default=None,
        ge=-2,
        le=2,
        description="Presence penalty (-2 to 2)",
    )
    frequency_penalty: Optional[float] = Field(
        default=None,
        ge=-2,
        le=2,
        description="Frequency penalty (-2 to 2)",
    )
    logit_bias: Optional[Dict[str, float]] = Field(
        default=None,
        description="Token logit bias",
    )
    user: Optional[str] = Field(
        default=None,
        description="A unique identifier for the end-user",
    )
    tools: Optional[List[ToolDefinition]] = Field(
        default=None,
        description="A list of tools the model may call",
    )
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        description="Controls which tool is called",
    )
    response_format: Optional[ResponseFormat] = Field(
        default=None,
        description="Response format specification",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for deterministic outputs",
    )


# =============================================================================
# Response Models
# =============================================================================


class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(..., description="Number of tokens in the completion")
    total_tokens: int = Field(..., description="Total number of tokens used")


class ChoiceMessage(BaseModel):
    """Message in a completion choice."""

    role: Literal["assistant"] = Field(default="assistant", description="The role of the author")
    content: Optional[str] = Field(default=None, description="The content of the message")
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None, description="Tool calls made by the assistant"
    )


class Choice(BaseModel):
    """A completion choice."""

    index: int = Field(..., description="The index of the choice")
    message: ChoiceMessage = Field(..., description="The generated message")
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = Field(
        default=None, description="The reason the model stopped generating"
    )


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str = Field(
        default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}",
        description="Unique identifier for the completion",
    )
    object: Literal["chat.completion"] = Field(
        default="chat.completion",
        description="Object type",
    )
    created: int = Field(
        default_factory=lambda: int(time.time()),
        description="Unix timestamp of creation",
    )
    model: str = Field(..., description="The model used for completion")
    choices: List[Choice] = Field(..., description="List of completion choices")
    usage: Optional[Usage] = Field(default=None, description="Token usage statistics")
    system_fingerprint: Optional[str] = Field(
        default=None, description="System fingerprint for reproducibility"
    )


# =============================================================================
# Streaming Response Models
# =============================================================================


class DeltaMessage(BaseModel):
    """Delta message in a streaming chunk."""

    role: Optional[Literal["assistant"]] = Field(
        default=None, description="The role of the author"
    )
    content: Optional[str] = Field(default=None, description="Content delta")
    tool_calls: Optional[List[ToolCall]] = Field(
        default=None, description="Tool call deltas"
    )


class StreamChoice(BaseModel):
    """A streaming completion choice."""

    index: int = Field(..., description="The index of the choice")
    delta: DeltaMessage = Field(..., description="The delta message")
    finish_reason: Optional[Literal["stop", "length", "tool_calls", "content_filter"]] = Field(
        default=None, description="The reason the model stopped generating"
    )


class ChatCompletionChunk(BaseModel):
    """OpenAI-compatible streaming chat completion chunk."""

    id: str = Field(..., description="Unique identifier for the completion")
    object: Literal["chat.completion.chunk"] = Field(
        default="chat.completion.chunk",
        description="Object type",
    )
    created: int = Field(..., description="Unix timestamp of creation")
    model: str = Field(..., description="The model used for completion")
    choices: List[StreamChoice] = Field(..., description="List of streaming choices")
    system_fingerprint: Optional[str] = Field(
        default=None, description="System fingerprint for reproducibility"
    )


# =============================================================================
# Helper Functions
# =============================================================================


def create_completion_id() -> str:
    """Generate a unique completion ID."""
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


def create_chunk(
    completion_id: str,
    model: str,
    created: int,
    content: Optional[str] = None,
    role: Optional[str] = None,
    finish_reason: Optional[str] = None,
    tool_calls: Optional[List[ToolCall]] = None,
) -> ChatCompletionChunk:
    """Create a streaming chunk."""
    delta = DeltaMessage(
        role=role if role else None,
        content=content,
        tool_calls=tool_calls,
    )
    return ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model,
        choices=[
            StreamChoice(
                index=0,
                delta=delta,
                finish_reason=finish_reason,
            )
        ],
    )

