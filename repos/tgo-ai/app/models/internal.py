"""
Internal data models for service integration and coordination logic.

This module defines models used internally by the supervisor agent
for representing data from external services and coordination state.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field
from app.runtime.tools.models import LLMProviderCredentials


class AgentTool(BaseModel):
    """Model representing an agent's tool configuration."""

    tool_id: UUID = Field(..., description="Tool ID")
    tool_name: str = Field(..., description="Tool name")
    tool_type: str = Field(..., description="Tool type (MCP or FUNCTION)")
    enabled: bool = Field(default=True, description="Whether tool is enabled for this agent")
    permissions: Optional[List[str]] = Field(default_factory=list, description="Tool permissions for this agent")
    tool_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Agent-specific tool configuration (overrides tool's default config)",
    )

    # MCP-specific fields (only populated for MCP tools)
    transport_type: Optional[str] = Field(None, description="Transport type for MCP tools (http, stdio, sse)")
    endpoint: Optional[str] = Field(None, description="Endpoint URL or command for MCP tools")
    base_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Base tool configuration from Tool model",
    )

    @property
    def input_schema(self) -> Dict[str, Any]:
        """获取工具的 inputSchema，优先从 base_config 获取"""
        if self.base_config:
            # 支持 inputSchema 和 input_schema 两种命名
            schema = self.base_config.get("inputSchema") or self.base_config.get("input_schema")
            if schema:
                return schema
        return {"type": "object", "properties": {}}

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class AgentCollection(BaseModel):
    """Model representing an agent's collection access."""

    id: UUID = Field(..., description="Internal association ID")
    collection_id: str = Field(..., description="External collection UUID")
    enabled: bool = Field(default=True, description="Whether collection is enabled for this agent")
    display_name: str = Field(..., description="Human-readable collection name")
    description: Optional[str] = Field(None, description="Collection description")
    collection_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Collection metadata")


    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class AgentWorkflow(BaseModel):
    """Model representing an agent's workflow access."""

    id: UUID = Field(..., description="Internal association ID")
    workflow_id: str = Field(..., description="External workflow service ID")
    enabled: bool = Field(default=True, description="Whether workflow is enabled for this agent")

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class Agent(BaseModel):
    """Model representing an AI agent from the AI Service."""

    id: UUID = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    instruction: Optional[str] = Field(None, description="Agent system instruction")
    model: str = Field(..., description="LLM model name")
    config: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration (temperature, max_tokens, markdown, etc.)")
    team_id: Optional[str] = Field(None, description="Associated team ID")
    tools: List[AgentTool] = Field(default_factory=list, description="Agent tools")
    collections: List[AgentCollection] = Field(default_factory=list, description="Agent collections")
    workflows: List[AgentWorkflow] = Field(default_factory=list, description="Agent workflows")
    is_default: bool = Field(default=False, description="Whether this is the default agent")
    is_remote_store_agent: bool = Field(default=False, description="Whether this is a remote agent from store")
    remote_agent_url: Optional[str] = Field(None, description="URL of the remote AgentOS server")
    store_agent_id: Optional[str] = Field(None, description="Agent ID in the remote store")
    agent_category: str = Field(default="normal", description="Agent category: normal or computer_use")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    llm_provider_credentials: Optional[LLMProviderCredentials] = Field(
        default=None,
        description="Resolved LLM provider credentials for this agent",
    )

    def get_capabilities(self) -> List[str]:
        """Get list of agent capabilities based on tools and instruction."""
        capabilities = []

        # Extract capabilities from tools
        for tool in self.tools:
            if tool.enabled:
                capabilities.append(tool.tool_name)

        # Extract capabilities from instruction (simplified keyword matching)
        if self.instruction:
            instruction_lower = self.instruction.lower()
            capability_keywords = [
                "support", "technical", "customer", "documentation", "search",
                "analysis", "coding", "writing", "translation", "math"
            ]
            for keyword in capability_keywords:
                if keyword in instruction_lower:
                    capabilities.append(keyword)

        return list(set(capabilities))  # Remove duplicates

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class Team(BaseModel):
    """Model representing a team from the AI Service."""

    id: str = Field(..., description="Team ID")
    name: str = Field(..., description="Team name")
    model: Optional[str] = Field(None, description="Team's default LLM model")
    instruction: Optional[str] = Field(None, description="Team system prompt/instructions")
    expected_output: Optional[str] = Field(None, description="Expected output format")
    config: Dict[str, Any] = Field(default_factory=dict, description="Team configuration")
    llm_provider_credentials: Optional[LLMProviderCredentials] = Field(
        default=None,
        description="Resolved LLM provider credentials for this team",
    )

    session_id: Optional[str] = Field(None, description="Team session identifier")
    is_default: bool = Field(default=False, description="Whether this is the default team")
    agents: List[Agent] = Field(default_factory=list, description="Team agents")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    def get_available_agents(self) -> List[Agent]:
        """Get list of available (non-deleted) agents."""
        return [agent for agent in self.agents if agent is not None]

    def get_default_agent(self) -> Optional[Agent]:
        """Get the default agent for this team."""
        for agent in self.agents:
            if agent.is_default:
                return agent
        return None

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class AgentExecutionRequest(BaseModel):
    """Model for agent execution requests to the Agent Service."""

    message: str = Field(..., description="Message to send to the agent")
    config: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    session_id: Optional[str] = Field(None, description="Session ID for conversation tracking")
    user_id: Optional[str] = Field(None, description="User ID for authentication")
    enable_memory: bool = Field(False, description="Enable agent memory for this execution")

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class AgentExecutionResponse(BaseModel):
    """Model for agent execution responses from the Agent Service."""

    messages: Optional[List[Dict[str, Any]]] = Field(None, description="Conversation messages")
    content: Optional[str] = Field(None, description="Agent response content")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Tool executions")
    success: bool = Field(default=True, description="Whether execution was successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Response metadata")

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class CoordinationContext(BaseModel):
    """Context information for agent coordination."""

    team: Team = Field(..., description="Team information")
    project_id: Optional[str] = Field(None, description="Project ID for cross-service integrations")
    message: str = Field(..., description="User message")
    system_message: Optional[str] = Field(None, description="Custom system message appended to team instructions for this run")

    expected_output: Optional[str] = Field(None, description="Expected output format to guide consolidation for this run")

    session_id: Optional[str] = Field(None, description="Session ID")
    user_id: Optional[str] = Field(None, description="User ID")
    execution_strategy: str = Field(..., description="Selected execution strategy")
    max_agents: int = Field(..., description="Maximum agents to execute")
    timeout: int = Field(..., description="Execution timeout")
    require_consensus: bool = Field(..., description="Whether consensus is required")
    mcp_url: Optional[str] = Field(None, description="URL of the MCP server for tool integration")
    rag_url: Optional[str] = Field(None, description="URL of the RAG server for retrieval-augmented generation")
    rag_api_key: Optional[str] = Field(None, description="API key for the RAG server")
    enable_memory: bool = Field(False, description="Enable conversational memory for downstream agents")

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class SubQuestion(BaseModel):
    """Model representing a decomposed sub-question from a complex query."""

    id: str = Field(..., description="Unique identifier for the sub-question")
    question: str = Field(..., description="The decomposed sub-question")
    intent: str = Field(..., description="The specific intent of this sub-question")
    priority: int = Field(..., ge=1, le=10, description="Priority level (1=highest, 10=lowest)")
    requires_context: bool = Field(default=False, description="Whether this sub-question requires context from other sub-questions")
    context_dependencies: List[str] = Field(default_factory=list, description="IDs of sub-questions this depends on")

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class QuestionDecomposition(BaseModel):
    """Model representing the decomposition of a complex question."""

    original_question: str = Field(..., description="The original user question")
    is_complex: bool = Field(..., description="Whether the question contains multiple intents")
    complexity_score: float = Field(..., ge=0.0, le=1.0, description="Complexity score (0=simple, 1=very complex)")
    sub_questions: List[SubQuestion] = Field(default_factory=list, description="Decomposed sub-questions")
    decomposition_reasoning: str = Field(..., description="Reasoning for the decomposition approach")

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class AgentAssignment(BaseModel):
    """Model representing an agent assignment to a specific sub-question."""

    sub_question_id: str = Field(..., description="ID of the sub-question")
    assigned_agent: Agent = Field(..., description="Agent assigned to handle this sub-question")
    assignment_reasoning: str = Field(..., description="Reasoning for this agent assignment")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in this assignment")

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"


class AgentSelection(BaseModel):
    """Model representing agent selection results."""

    selected_agents: List[Agent] = Field(..., description="Selected agents for execution")
    selection_strategy: str = Field(..., description="Strategy used for selection")
    selection_reasoning: str = Field(..., description="Reasoning for agent selection")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in selection")

    # Enhanced fields for multi-intent support
    question_decomposition: Optional[QuestionDecomposition] = Field(None, description="Question decomposition if applicable")
    agent_assignments: List[AgentAssignment] = Field(default_factory=list, description="Specific agent assignments to sub-questions")

    # Coordination planning result for sophisticated execution
    coordination_result: Optional[Any] = Field(None, description="Detailed coordination planning result from LLM")

    class Config:
        """Pydantic model configuration."""
        extra = "forbid"
