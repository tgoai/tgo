"""
Streaming response models for the TGO Supervisor Agent.

This module defines the event schema and models for real-time streaming
of coordination workflow progress to clients.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types for streaming coordination workflow."""
    
    # Workflow lifecycle events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    
    # Query analysis events
    QUERY_ANALYSIS_STARTED = "query_analysis_started"
    QUERY_ANALYSIS_PROGRESS = "query_analysis_progress"
    QUERY_ANALYSIS_COMPLETED = "query_analysis_completed"
    QUERY_ANALYSIS_FAILED = "query_analysis_failed"
    
    # Workflow planning events
    WORKFLOW_PLANNING_STARTED = "workflow_planning_started"
    WORKFLOW_PLANNING_COMPLETED = "workflow_planning_completed"
    WORKFLOW_PLANNING_FAILED = "workflow_planning_failed"
    
    # Agent execution events
    AGENT_EXECUTION_STARTED = "agent_execution_started"
    AGENT_EXECUTION_PROGRESS = "agent_execution_progress"
    AGENT_EXECUTION_COMPLETED = "agent_execution_completed"
    AGENT_EXECUTION_FAILED = "agent_execution_failed"
    
    # Batch execution events (for parallel/sequential patterns)
    BATCH_EXECUTION_STARTED = "batch_execution_started"
    BATCH_EXECUTION_PROGRESS = "batch_execution_progress"
    BATCH_EXECUTION_COMPLETED = "batch_execution_completed"
    
    # Result consolidation events
    CONSOLIDATION_STARTED = "consolidation_started"
    CONSOLIDATION_PROGRESS = "consolidation_progress"
    CONSOLIDATION_COMPLETED = "consolidation_completed"
    CONSOLIDATION_FAILED = "consolidation_failed"
    
    # Progress and status events
    PROGRESS_UPDATE = "progress_update"
    STATUS_UPDATE = "status_update"
    ERROR_EVENT = "error_event"
    WARNING_EVENT = "warning_event"

    # Agent-level streaming events (from agent service)
    AGENT_CONTENT_CHUNK = "agent_content_chunk"
    AGENT_TOOL_CALL_STARTED = "agent_tool_call_started"
    AGENT_TOOL_CALL_COMPLETED = "agent_tool_call_completed"
    AGENT_RESPONSE_COMPLETE = "agent_response_complete"

    # Team-level streaming events
    TEAM_RUN_STARTED = "team_run_started"
    TEAM_RUN_CONTENT = "team_run_content"
    TEAM_RUN_COMPLETED = "team_run_completed"
    TEAM_RUN_FAILED = "team_run_failed"
    TEAM_MEMBER_STARTED = "team_member_started"
    TEAM_MEMBER_CONTENT = "team_member_content"
    TEAM_MEMBER_COMPLETED = "team_member_completed"
    TEAM_MEMBER_FAILED = "team_member_failed"
    TEAM_MEMBER_TOOL_CALL_STARTED = "team_member_tool_call_started"
    TEAM_MEMBER_TOOL_CALL_COMPLETED = "team_member_tool_call_completed"

    # Deprecated legacy UI block events (no longer emitted in json-render mode)
    UI_BLOCK_STARTED = "ui_block_started"
    UI_BLOCK_CONTENT = "ui_block_content"
    UI_BLOCK_COMPLETED = "ui_block_completed"
    UI_BLOCK_ERROR = "ui_block_error"

    # json-render events (SpecStream protocol)
    JSON_RENDER_UPDATE = "json_render_update"


class EventSeverity(str, Enum):
    """Event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class BaseEventData(BaseModel):
    """Base class for all event data."""
    pass


class WorkflowStartedData(BaseEventData):
    """Data for workflow started event."""
    request_id: str
    agent_id: str
    agent_name: str
    session_id: Optional[str] = None
    message_length: int


class QueryAnalysisData(BaseEventData):
    """Data for query analysis events."""
    agent_name: str
    prompt_length: Optional[int] = None
    selected_agents: Optional[List[str]] = None
    workflow_pattern: Optional[str] = None
    confidence_score: Optional[float] = None
    is_complex: Optional[bool] = None
    sub_questions_count: Optional[int] = None


class WorkflowPlanningData(BaseEventData):
    """Data for workflow planning events."""
    pattern: str
    agent_count: int
    estimated_time: float
    parallel_groups: Optional[int] = None
    sequential_steps: Optional[int] = None
    hierarchical_levels: Optional[int] = None


class AgentExecutionData(BaseEventData):
    """Data for agent execution events."""
    agent_id: str
    agent_name: str
    execution_id: str
    question: str
    execution_time: Optional[float] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    response_length: Optional[int] = None


class BatchExecutionData(BaseEventData):
    """Data for batch execution events."""
    pattern: str
    total_agents: int
    completed_agents: int
    failed_agents: int
    current_batch: Optional[int] = None
    total_batches: Optional[int] = None


class ConsolidationData(BaseEventData):
    """Data for result consolidation events."""
    agent_id: str
    agent_name: str
    input_results_count: int
    consolidation_strategy: Optional[str] = None
    confidence_score: Optional[float] = None
    conflicts_resolved: Optional[int] = None
    response_length: Optional[int] = None


class ProgressUpdateData(BaseEventData):
    """Data for progress update events."""
    phase: str
    progress_percentage: float
    current_step: str
    total_steps: int
    completed_steps: int
    estimated_remaining_time: Optional[float] = None


class ErrorEventData(BaseEventData):
    """Data for error events."""
    error_type: str
    error_message: str
    component: str
    agent_id: Optional[str] = None
    execution_id: Optional[str] = None
    stack_trace: Optional[str] = None


class AgentContentChunkData(BaseEventData):
    """Data for agent content chunk events."""
    agent_id: str
    agent_name: str
    execution_id: str
    content_chunk: str
    chunk_index: int
    is_final: bool = False
    agent_role: Optional[str] = None


class AgentToolCallData(BaseEventData):
    """Data for agent tool call events."""
    agent_id: str
    agent_name: str
    execution_id: str
    tool_name: str
    tool_call_id: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    status: str  # started, completed, failed
    error: Optional[str] = None


class TeamRunLifecycleData(BaseEventData):
    """Data for high-level team run lifecycle events."""

    team_id: str
    team_name: str
    run_id: str
    session_id: Optional[str] = None
    message_length: Optional[int] = None


class TeamRunContentData(BaseEventData):
    """Data for team-level content events."""

    team_id: str
    team_name: str
    run_id: str
    content: Optional[str] = None
    content_type: str = "str"
    reasoning_content: Optional[str] = None
    is_intermediate: bool = False


class TeamRunCompletedData(BaseEventData):
    """Data for team run completion events."""

    team_id: str
    team_name: str
    run_id: str
    total_time: float
    content_length: Optional[int] = None
    content: Optional[str] = None


class TeamRunErrorData(BaseEventData):
    """Data for team run failure events."""

    team_id: str
    team_name: str
    run_id: Optional[str] = None
    error: str


class TeamMemberEventData(BaseEventData):
    """Data for team member lifecycle events."""

    team_id: str
    team_name: str
    member_id: str
    member_name: str
    member_role: Optional[str] = None
    run_id: str
    execution_time: Optional[float] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    response_length: Optional[int] = None
    content: Optional[str] = None


class TeamMemberContentData(BaseEventData):
    """Data for team member content streaming events."""

    team_id: str
    team_name: str
    member_id: str
    member_name: str
    member_role: Optional[str] = None
    run_id: str
    content_chunk: str
    chunk_index: int
    is_final: bool = False


class TeamMemberToolCallData(BaseEventData):
    """Data for team member tool call events."""

    team_id: str
    team_name: str
    member_id: str
    member_name: str
    member_role: Optional[str] = None
    run_id: str
    tool_name: str
    tool_call_id: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    status: str
    error: Optional[str] = None


class AgentResponseCompleteData(BaseEventData):
    """Data for agent response complete events."""
    agent_id: str
    agent_name: str
    execution_id: str
    final_content: str
    success: bool
    total_chunks: int
    tool_calls_count: int = 0
    response_length: int


class ConsolidationProgressData(BaseEventData):
    """Data for consolidation progress events."""
    current_step: str
    progress_percentage: float
    total_results: int
    processed_results: int
    estimated_remaining_time: Optional[float] = None
    consolidation_strategy: Optional[str] = None
    conflicts_detected: int = 0
    conflicts_resolved: int = 0


class UIBlockStartedData(BaseEventData):
    """Data for UI block started events."""

    block_id: str = Field(..., description="Unique identifier for this UI block")
    template_type: Optional[str] = Field(
        default=None,
        description="Expected template type (if known from context)",
    )
    agent_id: Optional[str] = Field(default=None, description="Agent that generated the block")
    agent_name: Optional[str] = Field(default=None, description="Name of the agent")


class UIBlockContentData(BaseEventData):
    """Data for UI block content streaming events."""

    block_id: str = Field(..., description="Unique identifier for this UI block")
    content_chunk: str = Field(..., description="Partial JSON content of the UI block")
    chunk_index: int = Field(..., description="Index of this chunk")
    is_final: bool = Field(default=False, description="Whether this is the final chunk")


class UIBlockCompletedData(BaseEventData):
    """Data for UI block completed events."""

    block_id: str = Field(..., description="Unique identifier for this UI block")
    template_type: str = Field(..., description="Template type from the parsed JSON")
    data: Dict[str, Any] = Field(..., description="Parsed and validated UI block data")
    raw_content: str = Field(..., description="Raw JSON content of the UI block")
    is_valid: bool = Field(default=True, description="Whether the data passed validation")
    validation_errors: Optional[List[str]] = Field(
        default=None,
        description="Validation error messages if any",
    )


class UIBlockErrorData(BaseEventData):
    """Data for UI block error events."""

    block_id: str = Field(..., description="Unique identifier for this UI block")
    error_type: str = Field(..., description="Type of error (parse_error, validation_error, etc.)")
    error_message: str = Field(..., description="Error message")
    partial_content: Optional[str] = Field(
        default=None,
        description="Partial content received before error",
    )


class JsonRenderUpdateData(BaseEventData):
    """Data for json-render SpecStream patch updates."""

    patches: List[Dict[str, Any]] = Field(
        ..., description="Array of RFC 6902 JSON Patch lines for json-render SpecStream"
    )
    text_content: Optional[str] = Field(
        default=None,
        description="Optional conversational text that preceded the json-render delimiter",
    )


class StreamingEvent(BaseModel):
    """A single streaming event in the coordination workflow."""
    
    event_type: EventType = Field(..., description="Type of the event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    correlation_id: str = Field(..., description="Correlation ID for tracking related events")
    request_id: str = Field(..., description="Request ID for the coordination workflow")
    severity: EventSeverity = Field(default=EventSeverity.INFO, description="Event severity level")
    
    data: Union[
        WorkflowStartedData,
        QueryAnalysisData,
        WorkflowPlanningData,
        AgentExecutionData,
        BatchExecutionData,
        ConsolidationData,
        ConsolidationProgressData,
        ProgressUpdateData,
        ErrorEventData,
        AgentContentChunkData,
        AgentToolCallData,
        AgentResponseCompleteData,
        TeamRunLifecycleData,
        TeamRunContentData,
        TeamRunCompletedData,
        TeamRunErrorData,
        TeamMemberEventData,
        TeamMemberContentData,
        TeamMemberToolCallData,
        UIBlockStartedData,
        UIBlockContentData,
        UIBlockCompletedData,
        UIBlockErrorData,
        JsonRenderUpdateData,
        BaseEventData
    ] = Field(..., description="Event-specific data")
    
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class StreamingResponse(BaseModel):
    """Response model for streaming endpoints."""
    
    stream: bool = Field(default=False, description="Whether streaming is enabled")
    request_id: str = Field(..., description="Request ID for tracking")
    
    # For non-streaming responses, include the final result
    final_response: Optional[Dict[str, Any]] = Field(None, description="Final response for non-streaming requests")


class StreamingEventBuffer:
    """Buffer for managing streaming events."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.events: List[StreamingEvent] = []
        self._subscribers: List[Any] = []
    
    def add_event(self, event: StreamingEvent) -> None:
        """Add an event to the buffer."""
        self.events.append(event)
        
        # Maintain buffer size
        if len(self.events) > self.max_size:
            self.events = self.events[-self.max_size:]
        
        # Notify subscribers
        self._notify_subscribers(event)
    
    def _notify_subscribers(self, event: StreamingEvent) -> None:
        """Notify all subscribers of a new event."""
        for subscriber in self._subscribers[:]:  # Copy to avoid modification during iteration
            try:
                subscriber.send_event(event)
            except Exception:
                # Remove failed subscribers
                self._subscribers.remove(subscriber)
    
    def subscribe(self, subscriber: Any) -> None:
        """Subscribe to events."""
        self._subscribers.append(subscriber)
    
    def unsubscribe(self, subscriber: Any) -> None:
        """Unsubscribe from events."""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
    
    def get_events(self, since: Optional[datetime] = None) -> List[StreamingEvent]:
        """Get events since a specific timestamp."""
        if since is None:
            return self.events.copy()
        
        return [event for event in self.events if event.timestamp > since]
