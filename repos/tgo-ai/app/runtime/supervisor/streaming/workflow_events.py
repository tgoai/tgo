"""
Workflow event generation for streaming coordination progress.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.streaming import (
    EventType,
    EventSeverity,
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
    JsonRenderUpdateData,
)
from app.streaming.event_emitter import StreamingEventEmitter
from app.models.internal import AgentExecutionContext
from ..models.coordination import QueryAnalysisResult
from ..models.execution import ExecutionResult
from ..models.results import ConsolidationResult


class WorkflowEventEmitter:
    """Event emitter for coordination workflow events."""
    
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

        self.emitter.emit(
            EventType.WORKFLOW_STARTED,
            data,
            EventSeverity.INFO,
            metadata,
        )
    
    def emit_workflow_completed(self, total_time: float, agents_consulted: int) -> None:
        """Emit workflow completed event."""
        data = ProgressUpdateData(
            phase="completed",
            progress_percentage=100.0,
            current_step="Workflow completed",
            total_steps=4,
            completed_steps=4
        )
        
        self.emitter.emit(
            EventType.WORKFLOW_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            {
                "total_execution_time": total_time,
                "agents_consulted": agents_consulted
            }
        )
    
    def emit_workflow_failed(self, error: str, component: str) -> None:
        """Emit workflow failed event."""
        data = ErrorEventData(
            error_type="WorkflowError",
            error_message=error,
            component=component
        )
        
        self.emitter.emit(
            EventType.WORKFLOW_FAILED,
            data,
            EventSeverity.ERROR,
            {"phase": "error"}
        )
    
    def emit_query_analysis_started(self, agent_name: str, prompt_length: int) -> None:
        """Emit query analysis started event."""
        data = QueryAnalysisData(
            agent_name=agent_name,
            prompt_length=prompt_length
        )
        
        self.emitter.emit(
            EventType.QUERY_ANALYSIS_STARTED,
            data,
            EventSeverity.INFO,
            {"phase": "query_analysis", "step": 1}
        )
    
    def emit_query_analysis_completed(self, result: QueryAnalysisResult, analysis_time: float) -> None:
        """Emit query analysis completed event."""
        data = QueryAnalysisData(
            agent_name="Query Analysis Agent",
            selected_agents=[str(agent_id) for agent_id in result.selected_agent_ids],
            workflow_pattern=result.workflow,
            confidence_score=result.confidence_score,
            is_complex=result.is_complex,
            sub_questions_count=len(result.sub_questions)
        )
        
        self.emitter.emit(
            EventType.QUERY_ANALYSIS_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            {
                "phase": "query_analysis",
                "step": 1,
                "analysis_time": analysis_time,
                "progress_percentage": 25.0
            }
        )
    
    def emit_query_analysis_failed(self, error: str, agent_name: str) -> None:
        """Emit query analysis failed event."""
        data = ErrorEventData(
            error_type="QueryAnalysisError",
            error_message=error,
            component="query_analyzer"
        )
        
        self.emitter.emit(
            EventType.QUERY_ANALYSIS_FAILED,
            data,
            EventSeverity.ERROR,
            {"phase": "query_analysis", "agent_name": agent_name}
        )
    
    def emit_workflow_planning_started(self, pattern: str, agent_count: int) -> None:
        """Emit workflow planning started event."""
        data = WorkflowPlanningData(
            pattern=pattern,
            agent_count=agent_count,
            estimated_time=0.0  # Will be updated when completed
        )
        
        self.emitter.emit(
            EventType.WORKFLOW_PLANNING_STARTED,
            data,
            EventSeverity.INFO,
            {"phase": "workflow_planning", "step": 2}
        )
    
    def emit_workflow_planning_completed(self, pattern: str, agent_count: int, 
                                       estimated_time: float, **kwargs) -> None:
        """Emit workflow planning completed event."""
        data = WorkflowPlanningData(
            pattern=pattern,
            agent_count=agent_count,
            estimated_time=estimated_time,
            parallel_groups=kwargs.get('parallel_groups'),
            sequential_steps=kwargs.get('sequential_steps'),
            hierarchical_levels=kwargs.get('hierarchical_levels')
        )
        
        self.emitter.emit(
            EventType.WORKFLOW_PLANNING_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            {
                "phase": "workflow_planning",
                "step": 2,
                "progress_percentage": 50.0
            }
        )
    
    def emit_agent_execution_started(self, agent_id: str, agent_name: str, 
                                   execution_id: str, question: str) -> None:
        """Emit agent execution started event."""
        data = AgentExecutionData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            question=question
        )
        
        self.emitter.emit(
            EventType.AGENT_EXECUTION_STARTED,
            data,
            EventSeverity.INFO,
            {"phase": "execution", "step": 3}
        )
    
    def emit_agent_execution_completed(self, result: ExecutionResult) -> None:
        """Emit agent execution completed event."""
        data = AgentExecutionData(
            agent_id=result.agent_id,
            agent_name=result.agent_name,
            execution_id=result.execution_id,
            question=result.question,
            execution_time=result.execution_time,
            success=result.success,
            error=result.error,
            response_length=len(result.response) if result.response else 0
        )
        
        severity = EventSeverity.SUCCESS if result.success else EventSeverity.ERROR
        
        self.emitter.emit(
            EventType.AGENT_EXECUTION_COMPLETED,
            data,
            severity,
            {"phase": "execution", "step": 3}
        )
    
    def emit_batch_execution_started(self, pattern: str, total_agents: int) -> None:
        """Emit batch execution started event."""
        data = BatchExecutionData(
            pattern=pattern,
            total_agents=total_agents,
            completed_agents=0,
            failed_agents=0
        )
        
        self.emitter.emit(
            EventType.BATCH_EXECUTION_STARTED,
            data,
            EventSeverity.INFO,
            {"phase": "execution", "step": 3}
        )
    
    def emit_batch_execution_progress(self, pattern: str, total_agents: int,
                                    completed_agents: int, failed_agents: int) -> None:
        """Emit batch execution progress event."""
        data = BatchExecutionData(
            pattern=pattern,
            total_agents=total_agents,
            completed_agents=completed_agents,
            failed_agents=failed_agents
        )
        
        progress = (completed_agents + failed_agents) / total_agents * 100
        
        self.emitter.emit(
            EventType.BATCH_EXECUTION_PROGRESS,
            data,
            EventSeverity.INFO,
            {
                "phase": "execution",
                "step": 3,
                "progress_percentage": 50.0 + (progress * 0.25)  # 50-75% range
            }
        )
    
    def emit_consolidation_started(self, agent_id: str, agent_name: str, input_count: int) -> None:
        """Emit consolidation started event."""
        data = ConsolidationData(
            agent_id=agent_id,
            agent_name=agent_name,
            input_results_count=input_count
        )

        self.emitter.emit(
            EventType.CONSOLIDATION_STARTED,
            data,
            EventSeverity.INFO,
            {"phase": "consolidation", "step": 4}
        )
    
    def emit_consolidation_completed(self, result: ConsolidationResult, agent_id: str = "consolidation_agent") -> None:
        """Emit consolidation completed event."""
        data = ConsolidationData(
            agent_id=agent_id,
            agent_name="Result Consolidation Agent",
            input_results_count=0,  # Not available in result
            consolidation_strategy=result.consolidation_approach.value,
            confidence_score=result.confidence_score,
            conflicts_resolved=len(result.conflicts_resolved),
            response_length=len(result.consolidated_content)
        )
        
        self.emitter.emit(
            EventType.CONSOLIDATION_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            {
                "phase": "consolidation",
                "step": 4,
                "progress_percentage": 100.0
            }
        )

    def emit_consolidation_progress(self, current_step: str, progress_percentage: float,
                                  total_results: int, processed_results: int,
                                  consolidation_strategy: str = None,
                                  estimated_remaining_time: float = None,
                                  conflicts_detected: int = 0, conflicts_resolved: int = 0) -> None:
        """Emit consolidation progress event."""
        data = ConsolidationProgressData(
            current_step=current_step,
            progress_percentage=progress_percentage,
            total_results=total_results,
            processed_results=processed_results,
            estimated_remaining_time=estimated_remaining_time,
            consolidation_strategy=consolidation_strategy,
            conflicts_detected=conflicts_detected,
            conflicts_resolved=conflicts_resolved
        )

        self.emitter.emit(
            EventType.CONSOLIDATION_PROGRESS,
            data,
            EventSeverity.INFO,
            {
                "phase": "consolidation",
                "step": 4,
                "progress_percentage": progress_percentage,
                "current_step": current_step
            }
        )

    def emit_progress_update(self, phase: str, progress: float, current_step: str,
                           total_steps: int, completed_steps: int) -> None:
        """Emit general progress update event."""
        data = ProgressUpdateData(
            phase=phase,
            progress_percentage=progress,
            current_step=current_step,
            total_steps=total_steps,
            completed_steps=completed_steps
        )
        
        self.emitter.emit(
            EventType.PROGRESS_UPDATE,
            data,
            EventSeverity.INFO,
            {"phase": phase}
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
            {"phase": "agent_execution", "agent_id": agent_id}
        )

    def emit_agent_tool_call_started(self, agent_id: str, agent_name: str, execution_id: str,
                                   tool_name: str, tool_call_id: str = None, tool_input: dict = None) -> None:
        """Emit agent tool call started event."""
        data = AgentToolCallData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_input=tool_input,
            status="started"
        )

        self.emitter.emit(
            EventType.AGENT_TOOL_CALL_STARTED,
            data,
            EventSeverity.INFO,
            {"phase": "agent_execution", "agent_id": agent_id, "tool_name": tool_name}
        )

    def emit_agent_tool_call_completed(self, agent_id: str, agent_name: str, execution_id: str,
                                     tool_name: str, tool_call_id: str = None,tool_input: dict = None, tool_output: str = None) -> None:
        """Emit agent tool call completed event."""
        data = AgentToolCallData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status="completed",
            tool_input=tool_input,
            tool_output=tool_output
        )

        self.emitter.emit(
            EventType.AGENT_TOOL_CALL_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            {"phase": "agent_execution", "agent_id": agent_id, "tool_name": tool_name}
        )

    def emit_agent_response_complete(self, agent_id: str, agent_name: str, execution_id: str,
                                   final_content: str, success: bool, total_chunks: int,
                                   tool_calls_count: int = 0) -> None:
        """Emit agent response complete event."""
        data = AgentResponseCompleteData(
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            final_content=final_content,
            success=success,
            total_chunks=total_chunks,
            tool_calls_count=tool_calls_count,
            response_length=len(final_content)
        )

        severity = EventSeverity.SUCCESS if success else EventSeverity.ERROR

        self.emitter.emit(
            EventType.AGENT_RESPONSE_COMPLETE,
            data,
            severity,
            {"phase": "agent_execution", "agent_id": agent_id}
        )

    # Team-level events

    def emit_team_run_started(
        self,
        team_id: str,
        team_name: str,
        run_id: str,
        *,
        session_id: Optional[str] = None,
        message_length: Optional[int] = None,
    ) -> None:
        """Emit team run started event."""
        data = TeamRunLifecycleData(
            team_id=team_id,
            team_name=team_name,
            run_id=run_id,
            session_id=session_id,
            message_length=message_length,
        )

        metadata = {
            "phase": "team_run",
            "status": "started",
            "team_id": team_id,
            "run_id": run_id,
        }
        if session_id:
            metadata["session_id"] = session_id

        self.emitter.emit(
            EventType.TEAM_RUN_STARTED,
            data,
            EventSeverity.INFO,
            metadata,
        )

    def emit_team_run_content(
        self,
        team_id: str,
        team_name: str,
        run_id: str,
        content: Optional[str],
        *,
        content_type: str = "str",
        reasoning_content: Optional[str] = None,
        is_intermediate: bool = False,
    ) -> None:
        """Emit team run content event."""
        data = TeamRunContentData(
            team_id=team_id,
            team_name=team_name,
            run_id=run_id,
            content=content,
            content_type=content_type,
            reasoning_content=reasoning_content,
            is_intermediate=is_intermediate,
        )

        metadata = {
            "phase": "team_run",
            "team_id": team_id,
            "run_id": run_id,
            "is_intermediate": is_intermediate,
        }

        self.emitter.emit(
            EventType.TEAM_RUN_CONTENT,
            data,
            EventSeverity.INFO,
            metadata,
        )

    def emit_team_run_completed(
        self,
        team_id: str,
        team_name: str,
        run_id: str,
        total_time: float,
        *,
        content_length: Optional[int] = None,
        content: Optional[str] = None,
    ) -> None:
        """Emit team run completed event."""
        data = TeamRunCompletedData(
            team_id=team_id,
            team_name=team_name,
            run_id=run_id,
            total_time=total_time,
            content_length=content_length,
            content=content,
        )

        metadata = {
            "phase": "team_run",
            "status": "completed",
            "team_id": team_id,
            "run_id": run_id,
            "total_time": total_time,
        }

        if content_length is not None:
            metadata["content_length"] = content_length

        self.emitter.emit(
            EventType.TEAM_RUN_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            metadata,
        )

    def emit_team_run_failed(
        self,
        team_id: str,
        team_name: str,
        error: str,
        *,
        run_id: Optional[str] = None,
    ) -> None:
        """Emit team run failed event."""
        data = TeamRunErrorData(
            team_id=team_id,
            team_name=team_name,
            run_id=run_id,
            error=error,
        )

        metadata = {
            "phase": "team_run",
            "status": "failed",
            "team_id": team_id,
        }
        if run_id:
            metadata["run_id"] = run_id

        self.emitter.emit(
            EventType.TEAM_RUN_FAILED,
            data,
            EventSeverity.ERROR,
            metadata,
        )

    def emit_team_member_started(
        self,
        team_id: str,
        team_name: str,
        member_id: str,
        member_name: str,
        run_id: str,
        *,
        member_role: Optional[str] = None,
    ) -> None:
        """Emit team member started event."""
        data = TeamMemberEventData(
            team_id=team_id,
            team_name=team_name,
            member_id=member_id,
            member_name=member_name,
            member_role=member_role,
            run_id=run_id,
        )

        metadata = {
            "phase": "team_member",
            "status": "started",
            "team_id": team_id,
            "member_id": member_id,
            "run_id": run_id,
        }
        if member_role:
            metadata["member_role"] = member_role

        self.emitter.emit(
            EventType.TEAM_MEMBER_STARTED,
            data,
            EventSeverity.INFO,
            metadata,
        )

    def emit_team_member_content(
        self,
        team_id: str,
        team_name: str,
        member_id: str,
        member_name: str,
        run_id: str,
        content_chunk: str,
        chunk_index: int,
        *,
        member_role: Optional[str] = None,
        is_final: bool = False,
    ) -> None:
        """Emit team member content event."""
        data = TeamMemberContentData(
            team_id=team_id,
            team_name=team_name,
            member_id=member_id,
            member_name=member_name,
            member_role=member_role,
            run_id=run_id,
            content_chunk=content_chunk,
            chunk_index=chunk_index,
            is_final=is_final,
        )

        metadata = {
            "phase": "team_member",
            "team_id": team_id,
            "member_id": member_id,
            "run_id": run_id,
            "chunk_index": chunk_index,
            "is_final": is_final,
        }
        if member_role:
            metadata["member_role"] = member_role

        self.emitter.emit(
            EventType.TEAM_MEMBER_CONTENT,
            data,
            EventSeverity.INFO,
            metadata,
        )

    def emit_team_member_completed(
        self,
        team_id: str,
        team_name: str,
        member_id: str,
        member_name: str,
        run_id: str,
        *,
        member_role: Optional[str] = None,
        execution_time: Optional[float] = None,
        response_length: Optional[int] = None,
        content: Optional[str] = None,
    ) -> None:
        """Emit team member completed event."""
        data = TeamMemberEventData(
            team_id=team_id,
            team_name=team_name,
            member_id=member_id,
            member_name=member_name,
            member_role=member_role,
            run_id=run_id,
            execution_time=execution_time,
            success=True,
            response_length=response_length,
            content=content,
        )

        metadata = {
            "phase": "team_member",
            "status": "completed",
            "team_id": team_id,
            "member_id": member_id,
            "run_id": run_id,
        }
        if member_role:
            metadata["member_role"] = member_role
        if execution_time is not None:
            metadata["execution_time"] = execution_time
        if response_length is not None:
            metadata["response_length"] = response_length

        self.emitter.emit(
            EventType.TEAM_MEMBER_COMPLETED,
            data,
            EventSeverity.SUCCESS,
            metadata,
        )

    def emit_team_member_failed(
        self,
        team_id: str,
        team_name: str,
        member_id: str,
        member_name: str,
        run_id: str,
        error: str,
        *,
        member_role: Optional[str] = None,
        execution_time: Optional[float] = None,
    ) -> None:
        """Emit team member failed event."""
        data = TeamMemberEventData(
            team_id=team_id,
            team_name=team_name,
            member_id=member_id,
            member_name=member_name,
            member_role=member_role,
            run_id=run_id,
            execution_time=execution_time,
            success=False,
            error=error,
        )

        metadata = {
            "phase": "team_member",
            "status": "failed",
            "team_id": team_id,
            "member_id": member_id,
            "run_id": run_id,
        }
        if member_role:
            metadata["member_role"] = member_role
        if execution_time is not None:
            metadata["execution_time"] = execution_time

        self.emitter.emit(
            EventType.TEAM_MEMBER_FAILED,
            data,
            EventSeverity.ERROR,
            metadata,
        )

    def emit_team_member_tool_call_started(
        self,
        team_id: str,
        team_name: str,
        member_id: str,
        member_name: str,
        run_id: str,
        tool_name: str,
        *,
        member_role: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_input: Optional[dict] = None,
    ) -> None:
        """Emit team member tool call started event."""
        data = TeamMemberToolCallData(
            team_id=team_id,
            team_name=team_name,
            member_id=member_id,
            member_name=member_name,
            member_role=member_role,
            run_id=run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_input=tool_input,
            status="started",
        )

        metadata = {
            "phase": "team_member",
            "team_id": team_id,
            "member_id": member_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
        }
        if member_role:
            metadata["member_role"] = member_role

        self.emitter.emit(
            EventType.TEAM_MEMBER_TOOL_CALL_STARTED,
            data,
            EventSeverity.INFO,
            metadata,
        )

    def emit_team_member_tool_call_completed(
        self,
        team_id: str,
        team_name: str,
        member_id: str,
        member_name: str,
        run_id: str,
        tool_name: str,
        *,
        member_role: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_input: Optional[dict] = None,
        tool_output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Emit team member tool call completed event."""
        status = "completed" if error is None else "failed"
        severity = EventSeverity.SUCCESS if error is None else EventSeverity.ERROR

        data = TeamMemberToolCallData(
            team_id=team_id,
            team_name=team_name,
            member_id=member_id,
            member_name=member_name,
            member_role=member_role,
            run_id=run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_input=tool_input,
            tool_output=tool_output,
            status=status,
            error=error,
        )

        metadata = {
            "phase": "team_member",
            "team_id": team_id,
            "member_id": member_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "status": status,
        }
        if member_role:
            metadata["member_role"] = member_role
        if error:
            metadata["error"] = error

        self.emitter.emit(
            EventType.TEAM_MEMBER_TOOL_CALL_COMPLETED,
            data,
            severity,
            metadata,
        )


    # ----------------------------------------------------------- json-render
    def emit_json_render_update(
        self,
        *,
        patches: list[Dict[str, Any]],
        text_content: Optional[str] = None,
        team_id: Optional[str] = None,
        member_id: Optional[str] = None,
    ) -> None:
        """Emit a json-render update event carrying SpecStream patch lines."""
        data = JsonRenderUpdateData(
            patches=patches,
            text_content=text_content,
        )
        metadata: Dict[str, Any] = {"phase": "json_render"}
        if team_id:
            metadata["team_id"] = team_id
        if member_id:
            metadata["member_id"] = member_id

        self.emitter.emit(
            EventType.JSON_RENDER_UPDATE,
            data,
            EventSeverity.INFO,
            metadata,
        )


def create_workflow_events(event_emitter: StreamingEventEmitter) -> WorkflowEventEmitter:
    """Create a workflow event emitter."""
    return WorkflowEventEmitter(event_emitter)
