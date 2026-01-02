"""Workflow service proxy endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.common_responses import CREATE_RESPONSES, CRUD_RESPONSES, LIST_RESPONSES
from app.core.security import get_current_active_user
from app.models import Staff
from app.schemas.ai_workflows import (
    PaginatedWorkflowSummaryResponse,
    WorkflowCreate,
    WorkflowDuplicateRequest,
    WorkflowExecuteRequest,
    WorkflowExecution,
    WorkflowExecutionCancelResponse,
    WorkflowInDB,
    WorkflowUpdate,
    WorkflowValidationResponse,
    WorkflowValidateRequest,
    WorkflowVariablesResponse,
)
from app.services.workflow_client import workflow_client

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedWorkflowSummaryResponse,
    responses=LIST_RESPONSES,
    summary="List Workflows",
)
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc"),
    current_user: Staff = Depends(get_current_active_user),
) -> PaginatedWorkflowSummaryResponse:
    """List workflows from Workflow service."""
    data = await workflow_client.list_workflows(
        project_id=str(current_user.project_id),
        skip=skip,
        limit=limit,
        status=status,
        search=search,
        tags=tags,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return PaginatedWorkflowSummaryResponse.model_validate(data)


@router.post(
    "",
    response_model=WorkflowInDB,
    responses=CREATE_RESPONSES,
    status_code=201,
    summary="Create Workflow",
)
async def create_workflow(
    workflow_data: WorkflowCreate,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowInDB:
    """Create workflow in Workflow service."""
    data = await workflow_client.create_workflow(
        str(current_user.project_id), workflow_data.model_dump(by_alias=True)
    )
    return WorkflowInDB.model_validate(data)


@router.get(
    "/{workflow_id}",
    response_model=WorkflowInDB,
    responses=CRUD_RESPONSES,
    summary="Get Workflow",
)
async def get_workflow(
    workflow_id: str,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowInDB:
    """Get workflow from Workflow service."""
    data = await workflow_client.get_workflow(workflow_id, str(current_user.project_id))
    return WorkflowInDB.model_validate(data)


@router.put(
    "/{workflow_id}",
    response_model=WorkflowInDB,
    responses=CRUD_RESPONSES,
    summary="Update Workflow",
)
async def update_workflow(
    workflow_id: str,
    workflow_data: WorkflowUpdate,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowInDB:
    """Update workflow in Workflow service."""
    data = await workflow_client.update_workflow(
        workflow_id,
        str(current_user.project_id),
        workflow_data.model_dump(by_alias=True, exclude_none=True),
    )
    return WorkflowInDB.model_validate(data)


@router.delete(
    "/{workflow_id}",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Delete Workflow",
)
async def delete_workflow(
    workflow_id: str,
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """Delete workflow from Workflow service."""
    await workflow_client.delete_workflow(workflow_id, str(current_user.project_id))


@router.post(
    "/{workflow_id}/duplicate",
    response_model=WorkflowInDB,
    responses=CRUD_RESPONSES,
    summary="Duplicate Workflow",
)
async def duplicate_workflow(
    workflow_id: str,
    request: Optional[WorkflowDuplicateRequest] = None,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowInDB:
    """Duplicate workflow in Workflow service."""
    payload = request.model_dump(by_alias=True, exclude_none=True) if request else None
    data = await workflow_client.duplicate_workflow(
        workflow_id, str(current_user.project_id), payload
    )
    return WorkflowInDB.model_validate(data)


@router.post(
    "/validate",
    response_model=WorkflowValidationResponse,
    responses=CRUD_RESPONSES,
    summary="Validate Workflow Generic",
)
async def validate_workflow_generic(
    request: WorkflowValidateRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowValidationResponse:
    """Validate an arbitrary workflow graph (nodes/edges) in Workflow service."""
    data = await workflow_client.validate_workflow_generic(
        str(current_user.project_id), request.model_dump(by_alias=True)
    )
    return WorkflowValidationResponse.model_validate(data)


@router.post(
    "/{workflow_id}/validate",
    response_model=WorkflowValidationResponse,
    responses=CRUD_RESPONSES,
    summary="Validate Workflow",
)
async def validate_workflow(
    workflow_id: str,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowValidationResponse:
    """Validate an existing workflow by id in Workflow service."""
    data = await workflow_client.validate_workflow(workflow_id, str(current_user.project_id))
    return WorkflowValidationResponse.model_validate(data)


@router.post(
    "/{workflow_id}/publish",
    response_model=WorkflowInDB,
    responses=CRUD_RESPONSES,
    summary="Publish Workflow",
)
async def publish_workflow(
    workflow_id: str,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowInDB:
    """Publish a workflow in Workflow service."""
    data = await workflow_client.publish_workflow(workflow_id, str(current_user.project_id))
    return WorkflowInDB.model_validate(data)


@router.get(
    "/{workflow_id}/variables",
    response_model=WorkflowVariablesResponse,
    responses=CRUD_RESPONSES,
    summary="Get Workflow Variables",
)
async def get_workflow_variables(
    workflow_id: str,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowVariablesResponse:
    """Get available variables for a workflow in Workflow service."""
    data = await workflow_client.get_workflow_variables(
        workflow_id, str(current_user.project_id)
    )
    return WorkflowVariablesResponse.model_validate(data)


@router.post(
    "/{workflow_id}/execute",
    response_model=WorkflowExecution,
    summary="Execute Workflow",
)
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowExecution:
    """Execute workflow in Workflow service."""
    data = await workflow_client.execute_workflow(
        workflow_id, str(current_user.project_id), request.model_dump(by_alias=True)
    )
    return WorkflowExecution.model_validate(data)


@router.post(
    "/{workflow_id}/execute/stream",
    summary="Execute Workflow (Streaming)",
    description="""
执行工作流并以 Server-Sent Events (SSE) 形式实时推送执行事件。

### 事件流格式
每个消息以 `data: ` 开头，后跟 JSON 字符串，以 `\n\n` 结束。

### 事件类型与数据结构

#### 1. **workflow_started** (工作流启动)
- `workflow_run_id`: 本次运行的唯一 ID
- `data`:
    - `id`: 运行 ID
    - `workflow_id`: 工作流 ID
    - `inputs`: 初始输入参数
    - `created_at`: 开始时间戳

#### 2. **node_started** (节点开始)
- `data`:
    - `id`: 节点执行记录 ID
    - `node_id`: 节点在工作流中的 ID
    - `node_type`: 节点类型 (input, llm, agent, answer, etc.)
    - `title`: 节点名称
    - `index`: 执行步骤序号 (从1开始)

#### 3. **node_finished** (节点完成)
- `data`:
    - `id`: 节点执行记录 ID
    - `status`: 执行状态 ("succeeded" | "failed")
    - `inputs`: 节点接收到的输入
    - `outputs`: 节点产生的输出
    - `error`: 错误信息 (仅在失败时存在)
    - `elapsed_time`: 节点耗时 (秒)

#### 4. **workflow_finished** (工作流结束)
- `data`:
    - `status`: 整体执行状态 ("succeeded" | "failed")
    - `outputs`: 最终输出结果 (通常由 answer 节点提供)
    - `error`: 全局错误信息
    - `total_steps`: 执行的总节点数
    - `elapsed_time`: 整个工作流耗时 (秒)

### 注意事项：
- 响应头包含 `Content-Type: text/event-stream`。
- 客户端应使用能够处理流式输出的库（如 EventSource 或 Fetch API）。
- 即使连接中断，后端也会继续完成数据库中的状态记录。
""",
    responses={
        200: {
            "description": "SSE Event Stream",
            "content": {
                "text/event-stream": {
                    "example": "data: {\"event\": \"workflow_started\", \"workflow_run_id\": \"uuid-1\", \"data\": {\"id\": \"uuid-1\", \"workflow_id\": \"wf-1\", \"inputs\": {}, \"created_at\": 1735790000}}\n\ndata: {\"event\": \"node_started\", \"workflow_run_id\": \"uuid-1\", \"data\": {\"node_id\": \"node-1\", \"node_type\": \"llm\", \"title\": \"AI对话\", \"index\": 1}}\n\ndata: {\"event\": \"node_finished\", \"workflow_run_id\": \"uuid-1\", \"data\": {\"status\": \"succeeded\", \"outputs\": {\"text\": \"Hello\"}, \"elapsed_time\": 0.5}}\n\ndata: {\"event\": \"workflow_finished\", \"workflow_run_id\": \"uuid-1\", \"data\": {\"status\": \"succeeded\", \"outputs\": {\"result\": \"Hello\"}, \"total_steps\": 2}}\n\n"
                }
            },
        },
        404: {"description": "Workflow not found"},
    },
)
async def execute_workflow_stream(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> StreamingResponse:
    """Execute workflow and proxy SSE stream from Workflow service."""
    generator = await workflow_client.execute_workflow_stream(
        workflow_id, str(current_user.project_id), request.model_dump(by_alias=True)
    )
    return StreamingResponse(generator, media_type="text/event-stream")


@router.get(
    "/executions/{execution_id}",
    response_model=WorkflowExecution,
    summary="Get Execution Status",
)
async def get_execution(
    execution_id: str,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowExecution:
    """Get execution status from Workflow service."""
    data = await workflow_client.get_execution(execution_id, str(current_user.project_id))
    return WorkflowExecution.model_validate(data)


@router.get(
    "/{workflow_id}/executions",
    response_model=List[WorkflowExecution],
    summary="List Workflow Executions",
)
async def list_workflow_executions(
    workflow_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Staff = Depends(get_current_active_user),
) -> List[WorkflowExecution]:
    """List workflow executions from Workflow service."""
    data = await workflow_client.list_workflow_executions(
        workflow_id, str(current_user.project_id), skip=skip, limit=limit
    )
    return [WorkflowExecution.model_validate(item) for item in data]


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=WorkflowExecutionCancelResponse,
    responses=CRUD_RESPONSES,
    summary="Cancel Execution",
)
async def cancel_execution(
    execution_id: str,
    current_user: Staff = Depends(get_current_active_user),
) -> WorkflowExecutionCancelResponse:
    """Cancel a workflow execution in Workflow service."""
    data = await workflow_client.cancel_execution(execution_id, str(current_user.project_id))
    return WorkflowExecutionCancelResponse.model_validate(data)

