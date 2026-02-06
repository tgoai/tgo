"""Chat completion service for OpenAI-compatible API.

This service proxies chat completion requests to various LLM providers
based on the provider_kind from the LLMProvider table.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

import google.generativeai as genai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.exceptions import TGOAIServiceException
from app.models.llm_provider import LLMProvider
from app.models.tool import Tool
from app.schemas.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    ChoiceMessage,
    DeltaMessage,
    FunctionCall,
    FunctionDefinition,
    StreamChoice,
    ToolCall,
    ToolDefinition,
    Usage,
    create_completion_id,
)
from app.services.llm_provider_service import LLMProviderService
from app.services.rag_service import rag_service_client
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================


class ProviderNotFoundError(TGOAIServiceException):
    """Raised when the specified LLM provider is not found."""

    def __init__(self, provider_id: uuid.UUID):
        super().__init__(
            code="PROVIDER_NOT_FOUND",
            message=f"LLM provider with ID {provider_id} not found",
            details={"provider_id": str(provider_id)},
        )


class ProviderNotActiveError(TGOAIServiceException):
    """Raised when the specified LLM provider is not active."""

    def __init__(self, provider_id: uuid.UUID):
        super().__init__(
            code="PROVIDER_NOT_ACTIVE",
            message=f"LLM provider with ID {provider_id} is not active",
            details={"provider_id": str(provider_id)},
        )


class UnsupportedProviderError(TGOAIServiceException):
    """Raised when the provider kind is not supported."""

    def __init__(self, provider_kind: str):
        super().__init__(
            code="UNSUPPORTED_PROVIDER",
            message=f"Provider kind '{provider_kind}' is not supported",
            details={"provider_kind": provider_kind},
        )


class ChatCompletionError(TGOAIServiceException):
    """Raised when chat completion fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="CHAT_COMPLETION_ERROR",
            message=message,
            details=details or {},
        )


# =============================================================================
# Chat Service
# =============================================================================


class ChatService:
    """Service for handling chat completions via various LLM providers."""

    # Provider kind constants
    OPENAI_PROVIDERS = {"openai", "openai_compatible"}
    ANTHROPIC_PROVIDER = "anthropic"
    GOOGLE_PROVIDER = "google"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.provider_service = LLMProviderService(db)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def create_completion(
        self,
        request: ChatCompletionRequest,
        project_id: uuid.UUID,
    ) -> ChatCompletionResponse:
        """Create a non-streaming chat completion with optional agentic loop."""
        provider = await self._get_provider(request.provider_id, project_id)
        provider_kind = (provider.provider_kind or "").lower()

        # Merge tools from all sources
        merged_tools = await self._merge_tools(request, project_id)
        request.tools = merged_tools

        max_rounds = request.max_tool_rounds if request.max_tool_rounds is not None else 5

        self._logger.info(
            "Creating chat completion",
            provider_id=str(request.provider_id),
            provider_kind=provider_kind,
            model=request.model,
            tools_count=len(merged_tools) if merged_tools else 0,
            auto_execute_tools=request.auto_execute_tools,
            max_tool_rounds=max_rounds,
        )

        # When auto_execute_tools=False, behave like standard OpenAI API:
        # call LLM once and return the raw response (including any tool_calls).
        if not request.auto_execute_tools:
            if provider_kind in self.OPENAI_PROVIDERS:
                return await self._openai_completion(request, provider)
            elif provider_kind == self.ANTHROPIC_PROVIDER:
                return await self._anthropic_completion(request, provider)
            elif provider_kind == self.GOOGLE_PROVIDER:
                return await self._google_completion(request, provider)
            else:
                raise UnsupportedProviderError(provider_kind)

        # auto_execute_tools=True: run agentic loop with internal tool execution
        # Create tool executor and register tools
        executor = ToolExecutor(self.db, project_id)
        # Set context for plugin tools
        executor.set_context(
            visitor_id=request.user, # request.user contains visitor_id
            agent_id=str(request.agent_id) if hasattr(request, "agent_id") else None,
        )
        await executor.register_tools(request.tool_ids, request.collection_ids)

        total_usage = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        
        for round_idx in range(max_rounds):
            self._logger.debug(f"Starting tool round {round_idx + 1}/{max_rounds}")
            
            if provider_kind in self.OPENAI_PROVIDERS:
                response = await self._openai_completion(request, provider)
            elif provider_kind == self.ANTHROPIC_PROVIDER:
                response = await self._anthropic_completion(request, provider)
            elif provider_kind == self.GOOGLE_PROVIDER:
                response = await self._google_completion(request, provider)
            else:
                raise UnsupportedProviderError(provider_kind)

            # Update usage
            if response.usage:
                total_usage.prompt_tokens += response.usage.prompt_tokens
                total_usage.completion_tokens += response.usage.completion_tokens
                total_usage.total_tokens += response.usage.total_tokens

            # Check if there are tool calls in the first choice
            if not response.choices or not response.choices[0].message.tool_calls:
                response.usage = total_usage
                return response

            # We have tool calls. Execute them and add to messages.
            assistant_msg_content = response.choices[0].message.content
            tool_calls = response.choices[0].message.tool_calls
            
            # Add assistant message with tool calls to history
            request.messages.append(ChatMessage(
                role="assistant",
                content=assistant_msg_content,
                tool_calls=tool_calls
            ))

            # Execute tool calls in parallel
            execution_tasks = []
            for tc in tool_calls:
                execution_tasks.append(executor.execute(tc.function.name, tc.function.arguments))
            
            results = await asyncio.gather(*execution_tasks)

            # Add tool result messages to history
            for tc, result in zip(tool_calls, results):
                request.messages.append(ChatMessage(
                    role="tool",
                    name=tc.function.name,
                    content=result,
                    tool_call_id=tc.id
                ))
            
            # Continue to next round

        # If max rounds reached, do one final call without tools
        self._logger.warning(f"Reached max tool rounds ({max_rounds}), finishing without tools")
        request.tools = None
        if provider_kind in self.OPENAI_PROVIDERS:
            response = await self._openai_completion(request, provider)
        elif provider_kind == self.ANTHROPIC_PROVIDER:
            response = await self._anthropic_completion(request, provider)
        elif provider_kind == self.GOOGLE_PROVIDER:
            response = await self._google_completion(request, provider)
        else:
            raise UnsupportedProviderError(provider_kind)
            
        if response.usage:
            total_usage.prompt_tokens += response.usage.prompt_tokens
            total_usage.completion_tokens += response.usage.completion_tokens
            total_usage.total_tokens += response.usage.total_tokens
        response.usage = total_usage
        
        return response

    async def create_completion_stream(
        self,
        request: ChatCompletionRequest,
        project_id: uuid.UUID,
    ) -> AsyncIterator[str]:
        """Create a streaming chat completion with optional agentic loop."""
        provider = await self._get_provider(request.provider_id, project_id)
        provider_kind = (provider.provider_kind or "").lower()

        # Merge tools from all sources
        merged_tools = await self._merge_tools(request, project_id)
        request.tools = merged_tools

        max_rounds = request.max_tool_rounds if request.max_tool_rounds is not None else 5

        self._logger.info(
            "Creating streaming chat completion",
            provider_id=str(request.provider_id),
            provider_kind=provider_kind,
            model=request.model,
            tools_count=len(merged_tools) if merged_tools else 0,
            auto_execute_tools=request.auto_execute_tools,
            max_tool_rounds=max_rounds,
        )

        # When auto_execute_tools=False, behave like standard OpenAI API:
        # stream LLM response as-is (including tool_call chunks).
        if not request.auto_execute_tools:
            if provider_kind in self.OPENAI_PROVIDERS:
                stream_gen = self._openai_stream(request, provider)
            elif provider_kind == self.ANTHROPIC_PROVIDER:
                stream_gen = self._anthropic_stream(request, provider)
            elif provider_kind == self.GOOGLE_PROVIDER:
                stream_gen = self._google_stream(request, provider)
            else:
                raise UnsupportedProviderError(provider_kind)

            async for raw_chunk in stream_gen:
                yield raw_chunk
            return

        # auto_execute_tools=True: run agentic loop with internal tool execution
        # Create tool executor
        executor = ToolExecutor(self.db, project_id)
        await executor.register_tools(request.tool_ids, request.collection_ids)

        for round_idx in range(max_rounds):
            self._logger.debug(f"Starting streaming tool round {round_idx + 1}/{max_rounds}")
            
            current_tool_calls: Dict[int, Dict[str, Any]] = {}
            current_content = ""
            
            if provider_kind in self.OPENAI_PROVIDERS:
                stream_gen = self._openai_stream(request, provider)
            elif provider_kind == self.ANTHROPIC_PROVIDER:
                stream_gen = self._anthropic_stream(request, provider)
            elif provider_kind == self.GOOGLE_PROVIDER:
                stream_gen = self._google_stream(request, provider)
            else:
                raise UnsupportedProviderError(provider_kind)

            async for raw_chunk in stream_gen:
                if raw_chunk == "data: [DONE]\n\n":
                    continue

                yield raw_chunk
                
                # Extract tool calls for next round
                if raw_chunk.startswith("data: "):
                    data_str = raw_chunk[6:].strip()
                    if data_str == "[DONE]":
                        continue
                    try:
                        chunk_data = json.loads(data_str)
                        if chunk_data.get("object") == "chat.completion.chunk":
                            choices = chunk_data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                if delta.get("content"):
                                    current_content += delta["content"]
                                if delta.get("tool_calls"):
                                    for tc_delta in delta["tool_calls"]:
                                        idx = tc_delta.get("index", 0)
                                        if idx not in current_tool_calls:
                                            current_tool_calls[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                                        if tc_delta.get("id"):
                                            current_tool_calls[idx]["id"] += tc_delta["id"]
                                        if tc_delta.get("function"):
                                            f_delta = tc_delta["function"]
                                            if f_delta.get("name"):
                                                current_tool_calls[idx]["function"]["name"] += f_delta["name"]
                                            if f_delta.get("arguments"):
                                                current_tool_calls[idx]["function"]["arguments"] += f_delta["arguments"]
                    except Exception:
                        pass

            if not current_tool_calls:
                yield "data: [DONE]\n\n"
                return

            # Prepare for next round
            final_tool_calls = []
            for idx in sorted(current_tool_calls.keys()):
                tc_info = current_tool_calls[idx]
                final_tool_calls.append(ToolCall(
                    id=tc_info["id"],
                    type="function",
                    function=FunctionCall(
                        name=tc_info["function"]["name"],
                        arguments=tc_info["function"]["arguments"]
                    )
                ))

            request.messages.append(ChatMessage(
                role="assistant",
                content=current_content,
                tool_calls=final_tool_calls
            ))

            for tc in final_tool_calls:
                yield f"data: {json.dumps({'type': 'tool_call', 'tool_call': tc.model_dump()}, ensure_ascii=False)}\n\n"

            execution_tasks = [executor.execute(tc.function.name, tc.function.arguments) for tc in final_tool_calls]
            results = await asyncio.gather(*execution_tasks)
            
            for tc, result in zip(final_tool_calls, results):
                yield f"data: {json.dumps({'type': 'tool_result', 'tool_call_id': tc.id, 'result': result}, ensure_ascii=False)}\n\n"
                request.messages.append(ChatMessage(
                    role="tool",
                    name=tc.function.name,
                    content=result,
                    tool_call_id=tc.id
                ))
            
            if round_idx == max_rounds - 1:
                self._logger.warning(f"Reached max tool rounds ({max_rounds}), finishing")
                break

        # Final call without tools if we broke out of the loop with tool calls
        if current_tool_calls and round_idx == max_rounds - 1:
            request.tools = None
            if provider_kind in self.OPENAI_PROVIDERS:
                stream_gen = self._openai_stream(request, provider)
            elif provider_kind == self.ANTHROPIC_PROVIDER:
                stream_gen = self._anthropic_stream(request, provider)
            elif provider_kind == self.GOOGLE_PROVIDER:
                stream_gen = self._google_stream(request, provider)
            else:
                raise UnsupportedProviderError(provider_kind)
            
            async for raw_chunk in stream_gen:
                yield raw_chunk
        else:
            yield "data: [DONE]\n\n"

    # -------------------------------------------------------------------------
    # Tool Merging Logic
    # -------------------------------------------------------------------------

    async def _merge_tools(
        self,
        request: ChatCompletionRequest,
        project_id: uuid.UUID,
    ) -> Optional[List[ToolDefinition]]:
        """Merge tools from request.tools, tool_ids, and collection_ids."""
        import asyncio
        
        db_tools_task = None
        if request.tool_ids:
            db_tools_task = asyncio.create_task(self._load_tools_from_db(request.tool_ids, project_id))

        rag_tools_task = None
        if request.collection_ids:
            rag_tools_task = asyncio.create_task(self._create_rag_tool_definitions(request.collection_ids, project_id))

        db_tools = await db_tools_task if db_tools_task else []
        rag_tools = await rag_tools_task if rag_tools_task else []

        # Merge all tools
        merged_tools: List[ToolDefinition] = []
        if request.tools:
            merged_tools.extend(request.tools)
        
        merged_tools.extend(db_tools)
        merged_tools.extend(rag_tools)

        return merged_tools if merged_tools else None

    async def _load_tools_from_db(
        self,
        tool_ids: List[uuid.UUID],
        project_id: uuid.UUID,
    ) -> List[ToolDefinition]:
        """Load MCP tools from database and convert to ToolDefinition."""
        if not tool_ids:
            return []

        stmt = select(Tool).where(
            and_(
                Tool.id.in_(tool_ids),
                Tool.project_id == project_id,
                Tool.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        tools = result.scalars().all()

        tool_defs = []
        for tool in tools:
            # We expect tool.config to contain 'inputSchema' for MCP tools
            parameters = tool.config.get("inputSchema", {}) if tool.config else {}
            
            tool_defs.append(
                ToolDefinition(
                    type="function",
                    function=FunctionDefinition(
                        name=tool.name,
                        description=tool.description,
                        parameters=parameters,
                    ),
                )
            )
        
        return tool_defs

    async def _create_rag_tool_definitions(
        self,
        collection_ids: List[str],
        project_id: uuid.UUID,
    ) -> List[ToolDefinition]:
        """Fetch collection info from RAG service and create RAG tool definitions."""
        if not collection_ids:
            return []

        tool_defs = []
        try:
            # We use the batch client to fetch info for all collections
            batch_resp = await rag_service_client.get_collections_batch(
                collection_ids, str(project_id)
            )
            
            # Map of found collections
            found_collections = {str(c.id): c for c in batch_resp.collections}

            for cid in collection_ids:
                if cid in found_collections:
                    col = found_collections[cid]
                    display_name = col.display_name
                    description = col.description or f"Search in {display_name}"
                else:
                    display_name = f"collection_{cid[:8]}"
                    description = f"Search in collection {cid}"

                tool_name = f"rag_search_{cid.replace('-', '')[:8]}"
                tool_defs.append(
                    ToolDefinition(
                        type="function",
                        function=FunctionDefinition(
                            name=tool_name,
                            description=f"{description} (Semantically similar search)",
                            parameters={
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Natural language search query",
                                    }
                                },
                                "required": ["query"],
                            },
                        ),
                    )
                )
        except Exception as e:
            self._logger.warning("Failed to create RAG tool definitions", error=str(e))
            # Fallback to generic definitions if RAG service call fails
            for cid in collection_ids:
                tool_name = f"rag_search_{cid.replace('-', '')[:8]}"
                tool_defs.append(
                    ToolDefinition(
                        type="function",
                        function=FunctionDefinition(
                            name=tool_name,
                            description=f"Search in collection {cid} (Semantically similar search)",
                            parameters={
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Natural language search query",
                                    }
                                },
                                "required": ["query"],
                            },
                        ),
                    )
                )

        return tool_defs

    # -------------------------------------------------------------------------
    # Provider Validation
    # -------------------------------------------------------------------------

    async def _get_provider(
        self,
        provider_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> LLMProvider:
        """Get and validate the LLM provider."""
        provider = await self.provider_service.get_provider_by_id(provider_id)

        if not provider or provider.project_id != project_id:
            raise ProviderNotFoundError(provider_id)

        if not provider.is_active:
            raise ProviderNotActiveError(provider_id)

        return provider

    # -------------------------------------------------------------------------
    # OpenAI / OpenAI-Compatible Implementation
    # -------------------------------------------------------------------------

    def _create_openai_client(self, provider: LLMProvider) -> AsyncOpenAI:
        """Create an OpenAI client from provider credentials."""
        return AsyncOpenAI(
            api_key=provider.api_key,
            base_url=provider.api_base_url,
            organization=provider.organization,
            timeout=provider.timeout or 60.0,
        )

    async def _openai_completion(
        self,
        request: ChatCompletionRequest,
        provider: LLMProvider,
    ) -> ChatCompletionResponse:
        """Handle OpenAI/OpenAI-compatible chat completion."""
        try:
            client = self._create_openai_client(provider)
            params = self._build_openai_params(request)
            response = await client.chat.completions.create(**params)

            return ChatCompletionResponse(
                id=response.id,
                created=response.created,
                model=response.model,
                choices=[
                    Choice(
                        index=choice.index,
                        message=ChoiceMessage(
                            role="assistant",
                            content=choice.message.content,
                            tool_calls=self._convert_openai_tool_calls(choice.message.tool_calls),
                        ),
                        finish_reason=choice.finish_reason,
                    )
                    for choice in response.choices
                ],
                usage=Usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                ) if response.usage else None,
                system_fingerprint=response.system_fingerprint,
            )
        except Exception as e:
            self._logger.error("OpenAI completion failed", error=str(e))
            raise ChatCompletionError(
                f"OpenAI completion failed: {e}",
                details={"provider_kind": "openai", "model": request.model},
            ) from e

    async def _openai_stream(
        self,
        request: ChatCompletionRequest,
        provider: LLMProvider,
    ) -> AsyncIterator[str]:
        """Handle OpenAI/OpenAI-compatible streaming chat completion."""
        try:
            client = self._create_openai_client(provider)
            params = self._build_openai_params(request)
            params["stream"] = True

            stream = await client.chat.completions.create(**params)

            async for chunk in stream:
                chunk_data = ChatCompletionChunk(
                    id=chunk.id,
                    created=chunk.created,
                    model=chunk.model,
                    choices=[
                        StreamChoice(
                            index=choice.index,
                            delta=DeltaMessage(
                                role=getattr(choice.delta, "role", None),
                                content=getattr(choice.delta, "content", None),
                                tool_calls=self._convert_openai_tool_calls(getattr(choice.delta, "tool_calls", None)),
                            ),
                            finish_reason=choice.finish_reason,
                        )
                        for choice in chunk.choices
                    ],
                    system_fingerprint=chunk.system_fingerprint,
                )
                yield f"data: {chunk_data.model_dump_json()}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            self._logger.error("OpenAI streaming failed", error=str(e))
            yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'api_error'}})}\n\n"

    def _convert_openai_tool_calls(self, openai_tool_calls: Optional[List[Any]]) -> Optional[List[ToolCall]]:
        """Convert OpenAI SDK tool calls to internal ToolCall schema."""
        if not openai_tool_calls:
            return None
        
        result = []
        for tc in openai_tool_calls:
            if isinstance(tc, dict):
                tc_index = tc.get("index")
                tc_id = tc.get("id")
                tc_type = tc.get("type", "function")
                func_data = tc.get("function")
                f_name = func_data.get("name") if func_data else None
                f_args = func_data.get("arguments") if func_data else None
            else:
                tc_index = getattr(tc, "index", None)
                tc_id = getattr(tc, "id", None)
                tc_type = getattr(tc, "type", "function")
                func_obj = getattr(tc, "function", None)
                f_name = getattr(func_obj, "name", None) if func_obj else None
                f_args = getattr(func_obj, "arguments", None) if func_obj else None
            
            result.append(ToolCall(
                index=tc_index,
                id=tc_id,
                type=tc_type,
                function=FunctionCall(
                    name=f_name,
                    arguments=f_args
                )
            ))
        return result if result else None

    def _build_openai_params(self, request: ChatCompletionRequest) -> Dict[str, Any]:
        """Build OpenAI API parameters from request."""
        params: Dict[str, Any] = {
            "model": request.model,
            "messages": [self._format_openai_message(msg) for msg in request.messages],
        }

        # Map optional parameters
        optional_params = {
            "temperature": request.temperature,
            "top_p": request.top_p,
            "n": request.n,
            "max_tokens": request.max_tokens,
            "stop": request.stop,
            "presence_penalty": request.presence_penalty,
            "frequency_penalty": request.frequency_penalty,
            "logit_bias": request.logit_bias,
            "user": request.user,
            "seed": request.seed,
        }

        for key, value in optional_params.items():
            if value is not None:
                params[key] = value

        # Handle complex parameters
        if request.tools:
            params["tools"] = [tool.model_dump() for tool in request.tools]
        if request.tool_choice is not None:
            params["tool_choice"] = request.tool_choice
        if request.response_format:
            params["response_format"] = request.response_format.model_dump()

        return params

    @staticmethod
    def _format_openai_message(msg: ChatMessage) -> Dict[str, Any]:
        """Format a single message for OpenAI API."""
        result: Dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.name:
            result["name"] = msg.name
        if msg.tool_calls:
            result["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
        if msg.tool_call_id:
            result["tool_call_id"] = msg.tool_call_id
        return result

    # -------------------------------------------------------------------------
    # Anthropic Implementation
    # -------------------------------------------------------------------------

    def _create_anthropic_client(self, provider: LLMProvider) -> AsyncAnthropic:
        """Create an Anthropic client from provider credentials."""
        return AsyncAnthropic(
            api_key=provider.api_key,
            timeout=provider.timeout or 60.0,
        )

    async def _anthropic_completion(
        self,
        request: ChatCompletionRequest,
        provider: LLMProvider,
    ) -> ChatCompletionResponse:
        """Handle Anthropic chat completion."""
        try:
            client = self._create_anthropic_client(provider)
            system_prompt, messages = self._convert_to_anthropic_messages(request.messages)
            params = self._build_anthropic_params(request, system_prompt, messages)

            response = await client.messages.create(**params)

            content = "".join(block.text for block in response.content if hasattr(block, "text"))
            finish_reason = "stop" if response.stop_reason == "end_turn" else response.stop_reason

            return ChatCompletionResponse(
                id=create_completion_id(),
                created=int(time.time()),
                model=response.model,
                choices=[
                    Choice(
                        index=0,
                        message=ChoiceMessage(role="assistant", content=content),
                        finish_reason=finish_reason,
                    )
                ],
                usage=Usage(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                ),
            )
        except Exception as e:
            self._logger.error("Anthropic completion failed", error=str(e))
            raise ChatCompletionError(
                f"Anthropic completion failed: {e}",
                details={"provider_kind": "anthropic", "model": request.model},
            ) from e

    async def _anthropic_stream(
        self,
        request: ChatCompletionRequest,
        provider: LLMProvider,
    ) -> AsyncIterator[str]:
        """Handle Anthropic streaming chat completion."""
        try:
            client = self._create_anthropic_client(provider)
            system_prompt, messages = self._convert_to_anthropic_messages(request.messages)
            params = self._build_anthropic_params(request, system_prompt, messages)

            completion_id = create_completion_id()
            created = int(time.time())
            first_chunk = True

            async with client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    chunk = self._create_stream_chunk(
                        completion_id, created, request.model,
                        content=text, role="assistant" if first_chunk else None,
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    first_chunk = False

            # Final chunk with finish_reason
            final_chunk = self._create_stream_chunk(
                completion_id, created, request.model, finish_reason="stop"
            )
            yield f"data: {final_chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            self._logger.error("Anthropic streaming failed", error=str(e))
            yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'api_error'}})}\n\n"

    def _build_anthropic_params(
        self,
        request: ChatCompletionRequest,
        system_prompt: Optional[str],
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build Anthropic API parameters."""
        params: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
        }

        if system_prompt:
            params["system"] = system_prompt
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.top_p is not None:
            params["top_p"] = request.top_p
        if request.stop:
            params["stop_sequences"] = request.stop if isinstance(request.stop, list) else [request.stop]

        # Handle tools for Anthropic
        if request.tools:
            anthropic_tools = []
            for tool in request.tools:
                if tool.type == "function":
                    anthropic_tools.append({
                        "name": tool.function.name,
                        "description": tool.function.description or "",
                        "input_schema": tool.function.parameters or {"type": "object", "properties": {}},
                    })
            if anthropic_tools:
                params["tools"] = anthropic_tools

        return params

    @staticmethod
    def _convert_to_anthropic_messages(
        messages: List[ChatMessage],
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """Convert OpenAI messages to Anthropic format."""
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            elif msg.role in ("user", "assistant"):
                anthropic_messages.append({"role": msg.role, "content": msg.content or ""})

        return system_prompt, anthropic_messages

    # -------------------------------------------------------------------------
    # Google Gemini Implementation
    # -------------------------------------------------------------------------

    @staticmethod
    def _configure_gemini(api_key: str) -> None:
        """Configure Gemini API with credentials."""
        genai.configure(api_key=api_key)

    async def _google_completion(
        self,
        request: ChatCompletionRequest,
        provider: LLMProvider,
    ) -> ChatCompletionResponse:
        """Handle Google Gemini chat completion."""
        try:
            self._configure_gemini(provider.api_key)
            
            # Build tools for Gemini
            tools = None
            if request.tools:
                gemini_functions = []
                for tool in request.tools:
                    if tool.type == "function":
                        gemini_functions.append({
                            "name": tool.function.name,
                            "description": tool.function.description or "",
                            "parameters": tool.function.parameters or {"type": "object", "properties": {}},
                        })
                if gemini_functions:
                    tools = [{"function_declarations": gemini_functions}]

            model = genai.GenerativeModel(request.model, tools=tools)
            history, last_message = self._convert_to_gemini_messages(request.messages)
            generation_config = self._build_gemini_config(request)

            chat = model.start_chat(history=history)
            response = await chat.send_message_async(
                last_message,
                generation_config=generation_config or None,
            )

            content = response.text
            # Estimate token counts
            prompt_tokens = sum(len(str(m.get("parts", [""])[0]).split()) for m in history) + len(last_message.split())
            completion_tokens = len(content.split())

            return ChatCompletionResponse(
                id=create_completion_id(),
                created=int(time.time()),
                model=request.model,
                choices=[
                    Choice(
                        index=0,
                        message=ChoiceMessage(role="assistant", content=content),
                        finish_reason="stop",
                    )
                ],
                usage=Usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
            )
        except Exception as e:
            self._logger.error("Google completion failed", error=str(e))
            raise ChatCompletionError(
                f"Google completion failed: {e}",
                details={"provider_kind": "google", "model": request.model},
            ) from e

    async def _google_stream(
        self,
        request: ChatCompletionRequest,
        provider: LLMProvider,
    ) -> AsyncIterator[str]:
        """Handle Google Gemini streaming chat completion."""
        try:
            self._configure_gemini(provider.api_key)
            
            # Build tools for Gemini
            tools = None
            if request.tools:
                gemini_functions = []
                for tool in request.tools:
                    if tool.type == "function":
                        gemini_functions.append({
                            "name": tool.function.name,
                            "description": tool.function.description or "",
                            "parameters": tool.function.parameters or {"type": "object", "properties": {}},
                        })
                if gemini_functions:
                    tools = [{"function_declarations": gemini_functions}]

            model = genai.GenerativeModel(request.model, tools=tools)
            history, last_message = self._convert_to_gemini_messages(request.messages)
            generation_config = self._build_gemini_config(request)

            chat = model.start_chat(history=history)
            completion_id = create_completion_id()
            created = int(time.time())
            first_chunk = True

            response = await chat.send_message_async(
                last_message,
                generation_config=generation_config or None,
                stream=True,
            )

            async for chunk in response:
                if chunk.text:
                    stream_chunk = self._create_stream_chunk(
                        completion_id, created, request.model,
                        content=chunk.text, role="assistant" if first_chunk else None,
                    )
                    yield f"data: {stream_chunk.model_dump_json()}\n\n"
                    first_chunk = False

            # Final chunk
            final_chunk = self._create_stream_chunk(
                completion_id, created, request.model, finish_reason="stop"
            )
            yield f"data: {final_chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            self._logger.error("Google streaming failed", error=str(e))
            yield f"data: {json.dumps({'error': {'message': str(e), 'type': 'api_error'}})}\n\n"

    @staticmethod
    def _build_gemini_config(request: ChatCompletionRequest) -> Dict[str, Any]:
        """Build Gemini generation config."""
        config: Dict[str, Any] = {}
        if request.temperature is not None:
            config["temperature"] = request.temperature
        if request.top_p is not None:
            config["top_p"] = request.top_p
        if request.max_tokens is not None:
            config["max_output_tokens"] = request.max_tokens
        if request.stop:
            config["stop_sequences"] = request.stop if isinstance(request.stop, list) else [request.stop]
        return config

    @staticmethod
    def _convert_to_gemini_messages(
        messages: List[ChatMessage],
    ) -> tuple[List[Dict[str, Any]], str]:
        """Convert OpenAI messages to Gemini format."""
        history: List[Dict[str, Any]] = []
        last_message = ""
        system_instruction = None

        for i, msg in enumerate(messages):
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                if i == len(messages) - 1:
                    last_message = msg.content or ""
                else:
                    history.append({"role": "user", "parts": [msg.content or ""]})
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content or ""]})

        # Prepend system instruction to last message if present
        if system_instruction:
            last_message = f"{system_instruction}\n\n{last_message}" if last_message else system_instruction

        return history, last_message

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _create_stream_chunk(
        completion_id: str,
        created: int,
        model: str,
        content: Optional[str] = None,
        role: Optional[str] = None,
        finish_reason: Optional[str] = None,
    ) -> ChatCompletionChunk:
        """Create a streaming chunk response."""
        return ChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model,
            choices=[
                StreamChoice(
                    index=0,
                    delta=DeltaMessage(role=role, content=content),
                    finish_reason=finish_reason,
                )
            ],
        )
