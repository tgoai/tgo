"""工具运行时内部使用的模型."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MCPConfig(BaseModel):
    """MCP服务器配置."""

    url: Optional[str] = Field(default=None, description="MCP服务URL")
    tools: Optional[List[str]] = Field(default=None, description="需要暴露的MCP工具列表")
    auth_required: bool = Field(default=False, description="是否需要鉴权")


class RagConfig(BaseModel):
    """RAG配置."""

    api_key: Optional[str] = Field(default=None, description="RAG服务API Key")
    rag_url: Optional[str] = Field(default=None, description="RAG服务地址")
    project_id: Optional[str] = Field(default=None, description="Project ID for RAG service calls")
    collections: Optional[List[str]] = Field(default=None, description="启用的集合列表")


class WorkflowConfig(BaseModel):
    """工作流配置."""

    workflow_url: Optional[str] = Field(default=None, description="工作流服务地址")
    project_id: Optional[str] = Field(default=None, description="Project ID for Workflow service calls")
    workflows: Optional[List[str]] = Field(default=None, description="启用的工作流ID列表")



class LLMProviderCredentials(BaseModel):
    """Typed structure for resolved LLM provider credentials."""

    provider_kind: str = Field(
        ..., description="openai | anthropic | google | openai_compatible"
    )
    api_key: str = Field(..., description="API key for the provider")
    api_base_url: Optional[str] = Field(
        default=None, description="Custom API base URL (for compatible vendors)"
    )
    organization: Optional[str] = Field(
        default=None, description="Organization/Tenant identifier"
    )
    timeout: Optional[float] = Field(
        default=None, description="Request timeout in seconds"
    )
    vendor: Optional[str] = Field(
        default=None, description="Vendor label (e.g., deepseek, openai, openrouter)"
    )

class AgentConfig(BaseModel):
    """单个智能体的模型配置."""

    model_name: Optional[str] = Field(default=None, description="模型标识")
    temperature: Optional[float] = Field(default=None, description="采样温度")
    max_tokens: Optional[int] = Field(default=None, description="最大生成token数")
    system_prompt: Optional[str] = Field(
        default=None,
        description="系统提示词",
    )
    mcp_config: Optional[MCPConfig] = Field(default=None, description="MCP配置")
    rag: Optional[RagConfig] = Field(default=None, description="RAG配置")
    workflow: Optional[WorkflowConfig] = Field(default=None, description="工作流配置")
    enable_memory: Optional[bool] = Field(default=None, description="是否为该智能体启用记忆功能")
    system_message: Optional[str] = Field(default=None, description="自定义系统消息")
    expected_output: Optional[str] = Field(default=None, description="期望的输出格式")

    # 扩展配置参数
    markdown: Optional[bool] = Field(default=None, description="是否使用markdown格式输出")
    add_datetime_to_context: Optional[bool] = Field(default=None, description="是否添加日期时间到上下文")
    add_location_to_context: Optional[bool] = Field(default=None, description="是否添加位置信息到上下文")
    timezone_identifier: Optional[str] = Field(default=None, description="时区标识")
    tool_call_limit: Optional[int] = Field(default=None, description="单次运行工具调用次数限制")
    num_history_runs: Optional[int] = Field(default=None, description="历史会话轮数限制")

    provider_credentials: Optional[LLMProviderCredentials] = Field(
        default=None,
        description="Resolved LLM provider credentials for this agent",
    )


class AgentRunRequest(BaseModel):
    """工具运行时执行请求."""

    message: str = Field(..., description="用户输入")

    config: Optional[AgentConfig] = Field(default=None, description="智能体执行配置")
    session_id: Optional[str] = Field(default=None, description="会话ID")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    stream: bool = Field(default=False, description="是否开启流式输出")
    stream_intermediate_steps: bool = Field(
        default=False,
        description="流式输出是否包含中间工具步骤",
    )
    enable_memory: bool = Field(default=False, description="是否启用会话记忆功能")


class ToolExecution(BaseModel):
    """单个工具调用的执行结果."""

    tool_call_id: Optional[str] = Field(default=None)
    tool_name: Optional[str] = Field(default=None)
    tool_args: Optional[Dict[str, Any]] = Field(default=None)
    tool_call_error: Optional[bool] = Field(default=False)
    result: Optional[str] = Field(default=None)


class AgentRunResponse(BaseModel):
    """工具智能体执行结果."""

    content: Optional[Any] = Field(default=None)
    tools: Optional[List[ToolExecution]] = Field(default=None)
    success: bool = Field(default=True)
    error: Optional[str] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class StreamEvent(BaseModel):
    """流式事件基类."""

    event: str = Field(...)
    timestamp: Optional[str] = Field(default=None)


class ContentStreamEvent(StreamEvent):
    event: str = Field(default="content")
    content: Optional[str] = Field(default=None)


class ToolCallStreamEvent(StreamEvent):
    event: str = Field(default="tool_call")
    tool_call_id: Optional[str] = Field(default=None)
    tool_name: str = Field(...)
    tool_input: Optional[Dict[str, Any]] = Field(default=None)
    tool_output: Optional[str] = Field(default=None)
    tool_call_error: Optional[bool] = Field(default=False)
    status: str = Field(default="started")


class ErrorStreamEvent(StreamEvent):
    event: str = Field(default="error")
    error: str = Field(...)
    error_type: Optional[str] = Field(default=None)


class CompleteStreamEvent(StreamEvent):
    event: str = Field(default="complete")
    final_response: Optional[AgentRunResponse] = Field(default=None)


StreamEventType = Union[
    ContentStreamEvent,
    ToolCallStreamEvent,
    ErrorStreamEvent,
    CompleteStreamEvent,
]
