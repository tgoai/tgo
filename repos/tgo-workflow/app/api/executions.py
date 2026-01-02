from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.execution import WorkflowExecution, NodeExecution
from app.schemas.execution import (
    WorkflowExecution as WorkflowExecutionSchema, 
    WorkflowExecuteRequest,
    WorkflowExecutionCancelResponse,
    WorkflowStartedEvent,
    NodeStartedEvent,
    NodeFinishedEvent,
    WorkflowFinishedEvent
)
from celery_app.celery import celery_app
from datetime import datetime
import time
import json
from celery_app.tasks import execute_workflow_task
from app.engine.executor import WorkflowExecutor
from app.services.workflow_service import WorkflowService
from app.core.logging import logger
from typing import List
import uuid

router = APIRouter()

@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionSchema)
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db)
):
    # Verify workflow exists and belongs to project
    from app.models.workflow import Workflow
    wf_query = select(Workflow).where(Workflow.id == workflow_id, Workflow.project_id == project_id)
    wf_result = await db.execute(wf_query)
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Create execution record
    execution_id = str(uuid.uuid4())
    db_execution = WorkflowExecution(
        id=execution_id,
        project_id=project_id,
        workflow_id=workflow_id,
        status="pending",
        input=request.inputs
    )
    db.add(db_execution)
    await db.commit()
    
    # Re-query with eager loading to avoid lazy loading issues
    stmt = (
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.node_executions))
        .where(WorkflowExecution.id == execution_id)
    )
    result = await db.execute(stmt)
    db_execution = result.scalar_one()
    
    # Trigger Celery task
    # Pass project_id to the task as well
    execute_workflow_task.delay(execution_id, workflow_id, request.inputs, project_id=project_id)
    
    return db_execution

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
                    "example": (
                        "data: {\"event\": \"workflow_started\", \"workflow_run_id\": \"uuid-1\", \"data\": {\"id\": \"uuid-1\", \"workflow_id\": \"wf-1\", \"inputs\": {}, \"created_at\": 1735790000}}\n\n"
                        "data: {\"event\": \"node_started\", \"workflow_run_id\": \"uuid-1\", \"data\": {\"node_id\": \"node-1\", \"node_type\": \"llm\", \"title\": \"AI对话\", \"index\": 1}}\n\n"
                        "data: {\"event\": \"node_finished\", \"workflow_run_id\": \"uuid-1\", \"data\": {\"status\": \"succeeded\", \"outputs\": {\"text\": \"Hello\"}, \"elapsed_time\": 0.5}}\n\n"
                        "data: {\"event\": \"workflow_finished\", \"workflow_run_id\": \"uuid-1\", \"data\": {\"status\": \"succeeded\", \"outputs\": {\"result\": \"Hello\"}, \"total_steps\": 2}}\n\n"
                    )
                }
            }
        },
        404: {"description": "Workflow not found"}
    }
)
async def execute_workflow_stream(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a workflow and stream the execution events using Server-Sent Events (SSE).
    """
    # 1. Verify workflow exists and belongs to project
    workflow = await WorkflowService.get_by_id(db, workflow_id, project_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # 2. Create execution record
    execution_id = str(uuid.uuid4())
    db_execution = WorkflowExecution(
        id=execution_id,
        project_id=project_id,
        workflow_id=workflow_id,
        status="running",
        input=request.inputs,
        started_at=datetime.utcnow()
    )
    db.add(db_execution)
    await db.commit()

    async def event_generator():
        start_time = time.time()
        task_id = f"stream-{execution_id}"
        
        # Emit workflow_started
        started_event = WorkflowStartedEvent(
            workflow_run_id=execution_id,
            task_id=task_id,
            data={
                "id": execution_id,
                "workflow_id": workflow_id,
                "inputs": request.inputs,
                "created_at": int(db_execution.started_at.timestamp())
            }
        )
        yield f"data: {started_event.model_dump_json()}\n\n"

        executor = WorkflowExecutor(workflow.definition, project_id=project_id)
        node_count = 0

        import asyncio
        queue = asyncio.Queue()

        # Re-defining callbacks to use the queue
        async def q_on_node_start(node_id, node_type, node_data, index):
            nonlocal node_count
            node_count += 1
            event = NodeStartedEvent(
                workflow_run_id=execution_id,
                task_id=task_id,
                data={
                    "id": str(uuid.uuid4()),
                    "node_id": node_id,
                    "node_type": node_type,
                    "title": node_data.get("title", node_type),
                    "index": index,
                    "created_at": int(time.time())
                }
            )
            await queue.put(f"data: {event.model_dump_json()}\n\n")

        async def q_on_node_complete(node_id, node_type, status, input, output, error, duration):
            # Save to DB
            node_exec_id = str(uuid.uuid4())
            node_exec = NodeExecution(
                id=node_exec_id,
                execution_id=execution_id,
                project_id=project_id,
                node_id=node_id,
                node_type=node_type,
                status=status,
                input=input,
                output=output,
                error=error,
                duration=duration,
                started_at=datetime.utcnow()
            )
            db.add(node_exec)
            await db.commit()

            event = NodeFinishedEvent(
                workflow_run_id=execution_id,
                task_id=task_id,
                data={
                    "id": node_exec_id,
                    "node_id": node_id,
                    "node_type": node_type,
                    "inputs": input,
                    "outputs": output,
                    "status": "succeeded" if status == "completed" else "failed",
                    "error": error,
                    "elapsed_time": duration / 1000.0,
                    "finished_at": int(time.time())
                }
            )
            await queue.put(f"data: {event.model_dump_json()}\n\n")

        status = "completed"
        error_msg = None
        final_output = None

        try:
            # Run executor in a separate task
            async def run_executor():
                nonlocal final_output, status, error_msg
                try:
                    final_output = await executor.run(request.inputs, on_node_start=q_on_node_start, on_node_complete=q_on_node_complete)
                except Exception as e:
                    status = "failed"
                    error_msg = str(e)
                    import traceback
                    logger.error(f"Workflow stream execution error: {traceback.format_exc()}")
                finally:
                    await queue.put(None) # Signal end

            executor_task = asyncio.create_task(run_executor())

            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item

        except Exception as e:
            status = "failed"
            error_msg = str(e)

        # 3. Update WorkflowExecution in DB
        duration = int((time.time() - start_time) * 1000)
        await db.execute(
            update(WorkflowExecution)
            .where(WorkflowExecution.id == execution_id)
            .values(
                status=status,
                output={"result": final_output} if final_output else None,
                error=error_msg,
                completed_at=datetime.utcnow(),
                duration=duration
            )
        )
        await db.commit()

        # 4. Emit workflow_finished
        finished_event = WorkflowFinishedEvent(
            workflow_run_id=execution_id,
            task_id=task_id,
            data={
                "id": execution_id,
                "workflow_id": workflow_id,
                "status": "succeeded" if status == "completed" else "failed",
                "outputs": {"result": final_output} if final_output else {},
                "error": error_msg,
                "elapsed_time": duration / 1000.0,
                "total_steps": node_count,
                "finished_at": int(time.time())
            }
        )
        yield f"data: {finished_event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/executions/{execution_id}", response_model=WorkflowExecutionSchema)
async def get_execution_status(
    execution_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.node_executions))
        .where(WorkflowExecution.id == execution_id, WorkflowExecution.project_id == project_id)
    )
    result = await db.execute(query)
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return execution

@router.get("/{workflow_id}/executions", response_model=List[WorkflowExecutionSchema])
async def get_workflow_executions(
    workflow_id: str,
    project_id: str = Query(..., description="Project ID"),
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.node_executions))
        .where(WorkflowExecution.workflow_id == workflow_id, WorkflowExecution.project_id == project_id)
        .order_by(desc(WorkflowExecution.started_at))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())

@router.post("/executions/{execution_id}/cancel", response_model=WorkflowExecutionCancelResponse)
async def cancel_execution(
    execution_id: str,
    project_id: str = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(WorkflowExecution)
        .where(WorkflowExecution.id == execution_id, WorkflowExecution.project_id == project_id)
    )
    result = await db.execute(query)
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
        
    if execution.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel execution in {execution.status} status")
        
    # Update status in DB
    execution.status = "cancelled"
    completed_at = datetime.utcnow()
    execution.completed_at = completed_at
    await db.commit()
    
    # Terminate Celery task if it's running
    celery_app.control.revoke(execution_id, terminate=True)
    
    return WorkflowExecutionCancelResponse(
        id=execution_id,
        status="cancelled",
        cancelled_at=completed_at
    )

