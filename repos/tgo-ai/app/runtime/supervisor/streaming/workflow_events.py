"""Workflow event generation for the single-agent supervisor runtime."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.models.internal import AgentExecutionContext
from app.models.streaming import (
    AgentContentChunkData,
    AgentExecutionData,
    AgentResponseCompleteData,
    AgentToolCallData,
    ErrorEventData,
    EventSeverity,
    EventType,
    JsonRenderUpdateData,
    ProgressUpdateData,
    WorkflowStartedData,
)
from app.streaming.event_emitter import StreamingEventEmitter


class WorkflowEventEmitter:
    """Event emitter for direct single-agent workflow progress."""

    def __init__(self, event_emitter: StreamingEventEmitter):
        self.emitter = event_emitter

    def emit_workflow_started(self, request_id: str, context: AgentExecutionContext) -> None:
        """Emit workflow started event."""
        data = WorkflowStartedData(
            request_id=request_id,
            agent_id=str(context.agent.id),
            agent_name=context.agent.name,
            session_id=context.session_id,
            message_length=len(context.message),
        )
        metadata = {
            "phase": "initialization",
            "agent_id": str(context.agent.id),
        }
        if context.session_id:
            metadata["session_id"] = context.session_id

        self.emitter.emit(EventType.WORKFLOW_STARTED, data, EventSeverity.INFO, metadata)

    def emit_workflow_completed(self, total_time: float, agents_consulted: int) -> None:
        """Emit workflow completed event."""
        data = ProgressUpdateData(
            phase="completed",
            progress_percentage=100.0,
            current_step="Workflow completed",
            total_steps=3,
            completed_steps=3,
        )
        self.emitter.emit(
            EventType.WORKFLOW_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            {
                "total_execution_time": total_time,
                "agents_consulted": agents_consulted,
            },
        )

    def emit_workflow_failed(self, error: str, component: str) -> None:
        """Emit workflow failed event."""
        data = ErrorEventData(
            error_type="WorkflowError",
            error_message=error,
            component=component,
        )
        self.emitter.emit(
            EventType.WORKFLOW_FAILED,
            data,
            EventSeverity.ERROR,
            {"phase": "error"},
        )

    def emit_agent_execution_started(
        self,
        agent_id: str,
        agent_name: str,
        execution_id: str,
        question: str,
    ) -> None:
        """Emit agent execution started event."""
        data = AgentExecutionData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            question=question,
        )
        self.emitter.emit(
            EventType.AGENT_EXECUTION_STARTED,
            data,
            EventSeverity.INFO,
            {"phase": "execution", "agent_id": agent_id},
        )

    def emit_agent_content_chunk(
        self,
        agent_id: str,
        agent_name: str,
        execution_id: str,
        content_chunk: str,
        chunk_index: int,
        is_final: bool = False,
        agent_role: Optional[str] = None,
    ) -> None:
        """Emit agent content chunk event."""
        data = AgentContentChunkData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            content_chunk=content_chunk,
            chunk_index=chunk_index,
            is_final=is_final,
            agent_role=agent_role,
        )
        self.emitter.emit(
            EventType.AGENT_CONTENT_CHUNK,
            data,
            EventSeverity.INFO,
            {"phase": "agent_execution", "agent_id": agent_id},
        )

    def emit_agent_tool_call_started(
        self,
        agent_id: str,
        agent_name: str,
        execution_id: str,
        tool_name: str,
        tool_call_id: Optional[str] = None,
        tool_input: Optional[dict] = None,
    ) -> None:
        """Emit agent tool call started event."""
        data = AgentToolCallData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_input=tool_input,
            status="started",
        )
        self.emitter.emit(
            EventType.AGENT_TOOL_CALL_STARTED,
            data,
            EventSeverity.INFO,
            {
                "phase": "agent_execution",
                "agent_id": agent_id,
                "tool_name": tool_name,
            },
        )

    def emit_agent_tool_call_completed(
        self,
        agent_id: str,
        agent_name: str,
        execution_id: str,
        tool_name: str,
        tool_call_id: Optional[str] = None,
        tool_input: Optional[dict] = None,
        tool_output: Optional[str] = None,
    ) -> None:
        """Emit agent tool call completed event."""
        data = AgentToolCallData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_input=tool_input,
            tool_output=tool_output,
            status="completed",
        )
        self.emitter.emit(
            EventType.AGENT_TOOL_CALL_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            {
                "phase": "agent_execution",
                "agent_id": agent_id,
                "tool_name": tool_name,
            },
        )

    def emit_agent_response_complete(
        self,
        agent_id: str,
        agent_name: str,
        execution_id: str,
        final_content: str,
        success: bool,
        total_chunks: int,
        tool_calls_count: int = 0,
    ) -> None:
        """Emit final agent response event."""
        data = AgentResponseCompleteData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            final_content=final_content,
            success=success,
            total_chunks=total_chunks,
            tool_calls_count=tool_calls_count,
            response_length=len(final_content),
        )
        severity = EventSeverity.SUCCESS if success else EventSeverity.ERROR
        self.emitter.emit(
            EventType.AGENT_RESPONSE_COMPLETE,
            data,
            severity,
            {"phase": "agent_execution", "agent_id": agent_id},
        )

    def emit_json_render_update(
        self,
        *,
        patches: list[Dict[str, Any]],
        text_content: Optional[str] = None,
        member_id: Optional[str] = None,
    ) -> None:
        """Emit a json-render update event carrying SpecStream patch lines."""
        data = JsonRenderUpdateData(patches=patches, text_content=text_content)
        metadata: Dict[str, Any] = {"phase": "json_render"}
        if member_id:
            metadata["member_id"] = member_id
        self.emitter.emit(EventType.JSON_RENDER_UPDATE, data, EventSeverity.INFO, metadata)



def create_workflow_events(event_emitter: StreamingEventEmitter) -> WorkflowEventEmitter:
    """Create a workflow event emitter."""
    return WorkflowEventEmitter(event_emitter)
