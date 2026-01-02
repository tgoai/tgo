from pydantic import BaseModel, JsonValue, Field
from typing import List, Optional, Dict, Literal
from datetime import datetime
from enum import Enum

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SSEEventType(str, Enum):
    WORKFLOW_STARTED = "workflow_started"
    NODE_STARTED = "node_started"
    NODE_FINISHED = "node_finished"
    WORKFLOW_FINISHED = "workflow_finished"

class WorkflowStartedEvent(BaseModel):
    event: Literal["workflow_started"] = Field("workflow_started")
    workflow_run_id: str = Field(..., description="Workflow execution ID")
    task_id: str = Field(..., description="Celery task ID or placeholder")
    data: Dict[str, JsonValue] = Field(..., description="Event data: id, workflow_id, inputs, created_at")

class NodeStartedEvent(BaseModel):
    event: Literal["node_started"] = Field("node_started")
    workflow_run_id: str = Field(..., description="Workflow execution ID")
    task_id: str = Field(..., description="Celery task ID or placeholder")
    data: Dict[str, JsonValue] = Field(..., description="Event data: id, node_id, node_type, title, index, created_at")

class NodeFinishedEvent(BaseModel):
    event: Literal["node_finished"] = Field("node_finished")
    workflow_run_id: str = Field(..., description="Workflow execution ID")
    task_id: str = Field(..., description="Celery task ID or placeholder")
    data: Dict[str, JsonValue] = Field(..., description="Event data: inputs, outputs, status, error, elapsed_time")

class WorkflowFinishedEvent(BaseModel):
    event: Literal["workflow_finished"] = Field("workflow_finished")
    workflow_run_id: str = Field(..., description="Workflow execution ID")
    task_id: str = Field(..., description="Celery task ID or placeholder")
    data: Dict[str, JsonValue] = Field(..., description="Event data: status, outputs, error, elapsed_time, total_steps")

class NodeExecutionBase(BaseModel):
    project_id: str = Field(..., description="Project ID")
    node_id: str = Field(..., description="The node ID in the workflow")
    node_type: str = Field(..., description="Node type")
    status: ExecutionStatus = Field(..., description="Execution status")
    input: Optional[Dict[str, JsonValue]] = Field(None, description="Input data for the node")
    output: Optional[Dict[str, JsonValue]] = Field(None, description="Output results for the node")
    error: Optional[str] = Field(None, description="Execution error message")
    started_at: datetime = Field(..., description="Node execution start time")
    completed_at: Optional[datetime] = Field(None, description="Node execution completion time")
    duration: Optional[int] = Field(None, description="Execution duration in milliseconds")

class NodeExecution(NodeExecutionBase):
    id: str = Field(..., description="Unique identifier for the node execution record")
    execution_id: str = Field(..., description="The ID of the parent workflow execution record")

    class Config:
        from_attributes = True

class WorkflowExecutionBase(BaseModel):
    project_id: str = Field(..., description="Project ID")
    workflow_id: str = Field(..., description="Workflow ID")
    status: ExecutionStatus = Field(..., description="Overall execution status")
    input: Optional[Dict[str, JsonValue]] = Field(None, description="Workflow startup input data")
    output: Optional[Dict[str, JsonValue]] = Field(None, description="Final workflow output result")
    error: Optional[str] = Field(None, description="Execution error message")
    started_at: datetime = Field(..., description="Workflow execution start time")
    completed_at: Optional[datetime] = Field(None, description="Workflow execution completion time")
    duration: Optional[int] = Field(None, description="Execution duration in milliseconds")

class WorkflowExecution(WorkflowExecutionBase):
    id: str = Field(..., description="Unique identifier for the workflow execution record")
    node_executions: List[NodeExecution] = Field([], description="List of detailed node executions")

    class Config:
        from_attributes = True

class WorkflowExecuteRequest(BaseModel):
    inputs: Dict[str, JsonValue] = Field(default={}, description="Input variables passed to the start node, where Key is the variable name")

class WorkflowExecutionCancelResponse(BaseModel):
    id: str = Field(..., description="Execution ID")
    status: ExecutionStatus = Field(..., description="Current status")
    cancelled_at: datetime = Field(..., description="Cancellation time")

