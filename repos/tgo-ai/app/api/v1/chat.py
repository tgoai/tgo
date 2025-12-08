"""OpenAI-compatible Chat Completions API endpoint.

This module provides a fully OpenAI-compatible chat completions endpoint
that proxies requests to various LLM providers based on the provider_id.
"""

import uuid
from typing import Union

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import build_error_responses
from app.core.logging import get_logger
from app.dependencies import get_db
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from app.services.chat_service import ChatService

logger = get_logger(__name__)

router = APIRouter()


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    """Get ChatService instance."""
    return ChatService(db)


_STREAMING_EXAMPLE = (
    'data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,'
    '"model":"gpt-4","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,'
    '"model":"gpt-4","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,'
    '"model":"gpt-4","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}\n\n'
    'data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,'
    '"model":"gpt-4","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
    "data: [DONE]\n\n"
)


_completions_success_responses = {
    200: {
        "description": "Successful response. Returns JSON when `stream=false` and Server-Sent Events when `stream=true`.",
        "content": {
            "application/json": {
                "schema": {
                    "$ref": "#/components/schemas/ChatCompletionResponse",
                },
                "example": {
                    "id": "chatcmpl-abc123",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "gpt-4",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Hello! How can I help you today?",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 8,
                        "total_tokens": 18,
                    },
                },
            },
            "text/event-stream": {
                "schema": {
                    "type": "string",
                    "description": "Server-Sent Events (SSE) stream in OpenAI format.",
                },
                "examples": {
                    "streaming_response": {
                        "summary": "Streaming response example",
                        "value": _STREAMING_EXAMPLE,
                    },
                },
            },
        },
    }
}


@router.post(
    "/completions",
    response_model=ChatCompletionResponse,
    responses={
        **_completions_success_responses,
        **build_error_responses(
            [400, 404, 500],
            {
                400: "Invalid request parameters",
                404: "LLM provider not found",
                500: "LLM API call failed",
            },
        ),
    },
    summary="Create chat completion",
    description="""
Create a chat completion using the specified LLM provider.

This endpoint is fully compatible with OpenAI's Chat Completions API format,
with the addition of `provider_id` for selecting LLM provider credentials.

**Request Parameters:**
- `provider_id` (UUID): The ID of the LLM provider to use (from ai_llm_providers table)
- `model` (string): The model identifier (e.g., "gpt-4", "claude-3-opus", "gemini-pro")
- `messages`: Array of conversation messages
- `stream`: Whether to stream the response (default: false)
- Other OpenAI-compatible parameters: temperature, max_tokens, etc.

**Provider Support:**
- `openai` / `openai_compatible`: Uses OpenAI SDK (supports custom base_url for compatible providers)
- `anthropic`: Uses Anthropic SDK
- `google`: Uses Google Generative AI SDK

**Streaming Response:**
When `stream=true`, returns Server-Sent Events in OpenAI format:
```
data: {"id":"...","object":"chat.completion.chunk",...}

data: [DONE]
```
""",
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    project_id: uuid.UUID = Query(..., description="Project ID for authorization"),
    chat_service: ChatService = Depends(get_chat_service),
) -> Union[ChatCompletionResponse, StreamingResponse]:
    """Create a chat completion.

    Supports both streaming and non-streaming responses based on the `stream` parameter.
    Uses the specified LLM provider credentials to proxy the request to the actual LLM API.
    """
    logger.info(
        "Chat completion request",
        project_id=str(project_id),
        provider_id=str(request.provider_id),
        model=request.model,
        stream=request.stream,
        message_count=len(request.messages),
    )

    if request.stream:
        return StreamingResponse(
            chat_service.create_completion_stream(request, project_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return await chat_service.create_completion(request, project_id)

