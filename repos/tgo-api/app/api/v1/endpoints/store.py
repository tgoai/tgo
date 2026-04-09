from typing import Any, List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_active_user
from app.core.logging import get_logger
from app.models.store_credential import StoreCredential
from app.models.staff import Staff
from app.schemas.store import (
    StoreCredential as StoreCredentialSchema, 
    StoreInstallRequest,
    StoreBindRequest,
    StoreAgentDetail,
    StoreToolSummary,
    AgentDependencyCheckResponse,
    StoreInstallAgentRequest
)
from app.schemas.tools import ToolCreateRequest, ToolType as CoreToolType, ToolSourceType
from app.utils.crypto import encrypt_str, decrypt_str
from app.services.store_client import store_client
from app.services.ai_client import ai_client
from app.services.ai_provider_sync import sync_provider_with_retry_and_update

logger = get_logger("endpoints.store")

router = APIRouter()


@router.post("/bind", response_model=StoreCredentialSchema)
async def bind_store(
    bind_in: StoreBindRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """
    绑定商店到当前项目
    1. 用 access_token 调用商店 /auth/api-key 获取 api_key
    2. 存储到 api_store_credentials
    """
    project_id = current_user.project_id
    # 1. 调用商店获取 api_key
    try:
        result = await store_client.get_api_key(bind_in.access_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch API Key from Store: {str(e)}"
        )

    # 2. 检查是否已存在凭证
    credential = db.scalar(
        select(StoreCredential).where(StoreCredential.project_id == project_id)
    )
    
    if credential:
        credential.store_user_id = result["user_id"]
        credential.store_email = result["email"]
        credential.api_key_encrypted = encrypt_str(result["api_key"])
    else:
        credential = StoreCredential(
            project_id=project_id,
            store_user_id=result["user_id"],
            store_email=result["email"],
            api_key_encrypted=encrypt_str(result["api_key"]),
        )
        db.add(credential)
    
    db.commit()
    db.refresh(credential)
    return credential


async def _install_tool_internal(resource_id: str, project_id: UUID, api_key: str) -> Any:
    """Internal helper to install a tool from store"""
    # 1. 调用商店 API 获取工具详情
    try:
        tool_detail = await store_client.get_tool(resource_id, api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch tool from Store: {str(e)}"
        )

    # 2. 构造本地工具创建请求
    config = tool_detail.get("config", {})
    # 确保 config 包含 inputSchema
    if "input_schema" in tool_detail and "inputSchema" not in config:
        config["inputSchema"] = tool_detail["input_schema"]
    
    # 存入 description 作为备份
    if (tool_detail.get("description_zh") or tool_detail.get("description")) and "description" not in config:
        config["description"] = tool_detail.get("description_zh") or tool_detail.get("description")

    tool_create = ToolCreateRequest(
        name=tool_detail["name"],
        title=tool_detail.get("title") or tool_detail.get("title_zh") or tool_detail["name"],
        title_zh=tool_detail.get("title_zh"),
        title_en=tool_detail.get("title_en"),
        description=tool_detail.get("description_zh") or tool_detail.get("description"),
        tool_type=CoreToolType.MCP,
        transport_type="http",
        endpoint=f"{settings.STORE_SERVICE_URL.rstrip('/')}/api/v1/mcp/{resource_id}/http",
        tool_source_type=ToolSourceType.STORE,
        store_resource_id=resource_id,
        config=config
    )

    # 3. 在 tgo-ai 创建 ai_tools 记录
    try:
        tool_data_dict = tool_create.model_dump(exclude_none=True)
        tool_data_dict["project_id"] = str(project_id)
        
        result = await ai_client.create_tool(tool_data=tool_data_dict)
        
        # 记录商店安装
        await store_client.install_tool(resource_id, api_key)
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tool in AI service: {str(e)}"
        )


async def _install_model_internal(resource_id: str, project_id: UUID, api_key: str, db: Session) -> Any:
    """Internal helper to install a model from store"""
    # 1. 调用商店 API 获取模型详情
    try:
        model_detail = await store_client.get_model(resource_id, api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch model from Store: {str(e)}"
        )

    # 2. 确保本地有一个 "Store" 类型的 LLMProvider
    from app.models import AIProvider
    provider_name = f"Store-{model_detail.provider.name}"
    local_model_id = model_detail.name

    provider = db.scalar(
        select(AIProvider).where(
            AIProvider.project_id == project_id,
            AIProvider.name == provider_name,
            AIProvider.deleted_at.is_(None)
        )
    )
    
    if not provider:
        provider = AIProvider(
            project_id=project_id,
            provider="openai_compatible",
            name=provider_name,
            api_base_url=f"{settings.STORE_SERVICE_URL.rstrip('/')}/api/v1",
            api_key=encrypt_str(api_key),
            is_active=True,
            default_model=local_model_id,
            is_from_store=True,
            store_resource_id=model_detail.provider.id
        )
        db.add(provider)
    else:
        provider.is_from_store = True
        provider.store_resource_id = model_detail.provider.id
        provider.api_base_url = f"{settings.STORE_SERVICE_URL.rstrip('/')}/api/v1"
        if not provider.default_model:
            provider.default_model = local_model_id
        db.add(provider)
    
    db.flush()

    # 3. 创建本地模型记录
    from app.models import AIModel
    existing_model = db.scalar(
        select(AIModel).where(
            AIModel.provider_id == provider.id,
            AIModel.model_id == local_model_id,
            AIModel.deleted_at.is_(None)
        )
    )
    
    if not existing_model:
        existing_model = AIModel(
            provider_id=provider.id,
            provider="openai_compatible",
            model_id=local_model_id,
            model_name=model_detail.title_zh or model_detail.name,
            model_type=model_detail.model_type,
            description=model_detail.description_zh,
            is_active=True,
            capabilities=model_detail.config.get("capabilities", {}) if model_detail.config else {},
            store_resource_id=resource_id
        )
        db.add(existing_model)
        # Ensure it's associated in the relationship for immediate sync
        if existing_model not in provider.models:
            provider.models.append(existing_model)
    else:
        existing_model.model_name = model_detail.title_zh or model_detail.name
        existing_model.model_type = model_detail.model_type
        existing_model.description = model_detail.description_zh
        existing_model.capabilities = model_detail.config.get("capabilities", {}) if model_detail.config else {}
        existing_model.store_resource_id = resource_id
        db.add(existing_model)
    
    # 记录商店安装
    try:
        await store_client.install_model(resource_id, api_key)
    except Exception as e:
        logger.warning(f"Failed to record installation in store: {str(e)}")
    
    db.commit()
    db.refresh(provider)

    # Sync provider to tgo-ai service
    ok, err = await sync_provider_with_retry_and_update(db, provider)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync provider to AI service: {err}"
        )

    return {"success": True, "model_id": local_model_id, "provider": provider_name}


@router.post("/install-tool", response_model=Any)
async def install_tool_from_store(
    install_in: StoreInstallRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """从商店安装工具到项目"""
    project_id = current_user.project_id
    # 1. 获取项目绑定的商店凭证
    credential = db.scalar(
        select(StoreCredential).where(StoreCredential.project_id == project_id)
    )
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project not bound to Store. Please bind credentials first."
        )
    
    api_key = decrypt_str(credential.api_key_encrypted)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt Store API Key"
        )

    return await _install_tool_internal(install_in.resource_id, project_id, api_key)


@router.delete("/uninstall-tool/{resource_id}")
async def uninstall_tool_from_store(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """从本地项目卸载商店工具"""
    project_id = current_user.project_id
    # 1. 查找本地匹配的商店工具
    local_tools = await ai_client.list_tools(project_id=str(project_id))
    target_tool = next((t for t in local_tools if t.get("store_resource_id") == resource_id), None)
    
    if not target_tool:
        raise HTTPException(status_code=404, detail="Tool not found in this project")

    # 2. 调用商店 API 记录卸载
    credential = db.scalar(
        select(StoreCredential).where(StoreCredential.project_id == project_id)
    )
    if credential:
        api_key = decrypt_str(credential.api_key_encrypted)
        if api_key:
            try:
                await store_client.uninstall_tool(resource_id, api_key)
            except Exception:
                # 商店卸载失败不影响本地卸载
                pass

    # 3. 在 tgo-ai 删除 ai_tools 记录
    try:
        await ai_client.delete_tool(
            project_id=str(project_id),
            tool_id=target_tool["id"]
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tool in AI service: {str(e)}"
        )

# --- Model Installation ---

@router.post("/install-model", response_model=Any)
async def install_model_from_store(
    install_in: StoreInstallRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """从商店安装模型到项目"""
    project_id = current_user.project_id
    # 1. 获取项目绑定的商店凭证
    credential = db.scalar(
        select(StoreCredential).where(StoreCredential.project_id == project_id)
    )
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project not bound to Store. Please bind credentials first."
        )
    
    api_key = decrypt_str(credential.api_key_encrypted)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt Store API Key"
        )

    return await _install_model_internal(install_in.resource_id, project_id, api_key, db)


@router.delete("/uninstall-model/{resource_id}")
async def uninstall_model_from_store(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """从本地项目卸载商店模型"""
    project_id = current_user.project_id
    
    # 1. 获取项目绑定的商店凭证
    credential = db.scalar(
        select(StoreCredential).where(StoreCredential.project_id == project_id)
    )
    if not credential:
        raise HTTPException(status_code=400, detail="Project not bound to Store")
        
    api_key = decrypt_str(credential.api_key_encrypted)
    if not api_key:
        raise HTTPException(status_code=500, detail="Failed to decrypt API Key")

    # 2. 调用商店 API 获取模型详情以获取本地标识符 (model_name)
    try:
        model_detail = await store_client.get_model(resource_id, api_key)
        local_model_id = model_detail.name
    except Exception as e:
        logger.error(f"Failed to fetch model detail from store during uninstall: {str(e)}")
        # 如果商店查不到，尝试从 resource_id 推断（这可能不准确，因为我们现在用 name 存）
        # 或者我们可以尝试在本地数据库找有没有前缀匹配的模型，但这不靠谱
        raise HTTPException(status_code=502, detail="Failed to fetch model info from store")

    # 3. 调用商店 API 记录卸载
    try:
        await store_client.uninstall_model(resource_id, api_key)
    except Exception as e:
        logger.warning(f"Failed to record uninstallation in store: {str(e)}")

    # 4. 从 AIProvider 关联的模型记录中移除
    from app.models import AIProvider, AIModel
    # 查找该项目的 Store Providers
    providers = db.scalars(
        select(AIProvider).where(
            AIProvider.project_id == project_id,
            AIProvider.name.like("Store-%"),
            AIProvider.deleted_at.is_(None)
        )
    ).all()
    
    for provider in providers:
        # 查找该 Provider 下的匹配模型
        model = db.scalar(
            select(AIModel).where(
                AIModel.provider_id == provider.id,
                AIModel.model_id == local_model_id,
                AIModel.deleted_at.is_(None)
            )
        )
        if model:
            db.delete(model)
            
            # 如果删掉的是默认模型，重新选一个或置空
            if provider.default_model == local_model_id:
                db.flush() # 确保 delete 已同步
                remaining = db.scalar(
                    select(AIModel.model_id).where(
                        AIModel.provider_id == provider.id,
                        AIModel.deleted_at.is_(None)
                    ).limit(1)
                )
                provider.default_model = remaining
                db.add(provider)
            
            # 记录需要同步的 Provider
            db.commit() # 先提交模型删除
            try:
                await sync_provider_with_retry_and_update(db, provider)
            except Exception as e:
                logger.warning(f"Failed to sync provider to AI service after model uninstall: {str(e)}")

    return {"success": True}


@router.get("/installed-models", response_model=List[str])
async def list_installed_models(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """列出当前项目已安装的所有商店模型 (仅返回标识符列表)"""
    project_id = current_user.project_id
    
    # 通过关联 Provider 查找已安装模型
    try:
        from app.models import AIProvider, AIModel
        
        # 我们只需要 model_id (即商店中的 name)
        # 显式转换为字符串列表，防止 Row 对象泄露
        model_ids = db.scalars(
            select(AIModel.model_id)
            .join(AIProvider, AIModel.provider_id == AIProvider.id)
            .where(
                AIProvider.project_id == project_id,
                AIProvider.name.like("Store-%"),
                AIModel.deleted_at.is_(None),
                AIProvider.deleted_at.is_(None)
            )
        ).all()
        return [str(mid) for mid in model_ids]
    except Exception as e:
        logger.error(f"Failed to list installed models: {str(e)}")
        return []


@router.get("/agent/{agent_id}/check-dependencies", response_model=AgentDependencyCheckResponse)
async def check_agent_dependencies(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """检查员工依赖的工具和模型是否已安装"""
    project_id = current_user.project_id
    
    # 1. 获取项目绑定的商店凭证
    credential = db.scalar(
        select(StoreCredential).where(StoreCredential.project_id == project_id)
    )
    if not credential:
        raise HTTPException(status_code=400, detail="Project not bound to Store")
    
    api_key = decrypt_str(credential.api_key_encrypted)
    if not api_key:
        raise HTTPException(status_code=500, detail="Failed to decrypt Store API Key")

    # 2. 调用商店 API 获取员工详情
    try:
        agent_template = await store_client.get_agent(agent_id, api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch agent template from Store: {str(e)}"
        )

    # 3. 检查已安装的工具
    local_tools = await ai_client.list_tools(project_id=str(project_id))
    installed_store_tool_ids = {t.get("store_resource_id") for t in local_tools if t.get("store_resource_id")}
    
    missing_tools = []
    if agent_template.recommended_tools:
        for tool_id in agent_template.recommended_tools:
            if tool_id not in installed_store_tool_ids:
                try:
                    tool_detail = await store_client.get_tool(tool_id, api_key)
                    missing_tools.append(StoreToolSummary(
                        id=tool_id,
                        name=tool_detail["name"],
                        title_zh=tool_detail.get("title_zh") or tool_detail.get("name"),
                        price_per_call=tool_detail.get("price_per_call", 0)
                    ))
                except Exception as e:
                    logger.warning(f"Failed to fetch tool {tool_id} details: {str(e)}")
                    # 即使获取失败也标记为缺失，只包含 ID 和基本占位
                    missing_tools.append(StoreToolSummary(
                        id=tool_id,
                        name="Unknown Tool",
                        title_zh=f"未知工具 ({tool_id[:8]})"
                    ))

    # 4. 检查已安装的模型
    from app.models import AIModel, AIProvider
    missing_model = None
    if agent_template.model_id:
        # 必须检查模型未删除且所属的 Provider 未删除，且属于当前项目
        existing_model = db.scalar(
            select(AIModel)
            .join(AIProvider, AIModel.provider_id == AIProvider.id)
            .where(AIModel.store_resource_id == agent_template.model_id)
            .where(AIModel.deleted_at.is_(None))
            .where(AIProvider.deleted_at.is_(None))
            .where(AIProvider.project_id == project_id)
        )
        if not existing_model:
            missing_model = agent_template.model

    return {
        "agent": agent_template,
        "missing_tools": missing_tools,
        "missing_model": missing_model
    }


@router.post("/install-agent", response_model=Any)
async def install_agent_from_store(
    install_in: StoreInstallAgentRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """从商店招聘 AI 员工到项目"""
    project_id = current_user.project_id
    # 1. 获取项目绑定的商店凭证
    credential = db.scalar(
        select(StoreCredential).where(StoreCredential.project_id == project_id)
    )
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project not bound to Store. Please bind credentials first."
        )
    
    api_key = decrypt_str(credential.api_key_encrypted)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt Store API Key"
        )

    # 2. 调用商店 API 获取 AgentTemplate 详情
    try:
        agent_template = await store_client.get_agent(install_in.resource_id, api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch agent template from Store: {str(e)}"
        )

    # 3. 批量安装选中的依赖并收集工具 ID
    installed_tool_bindings = []
    
    # 3.1 循环安装工具
    if agent_template.recommended_tools:
        # 获取最新的本地工具列表，以防某些工具已经安装
        local_tools = await ai_client.list_tools(project_id=str(project_id))
        store_to_local_id_map = {t.get("store_resource_id"): t.get("id") for t in local_tools if t.get("store_resource_id")}
        
        for tool_id in agent_template.recommended_tools:
            local_tool_id = store_to_local_id_map.get(tool_id)
            
            # 如果不在本地且被用户选中安装，或者已经在本地
            should_install = install_in.install_tool_ids and tool_id in install_in.install_tool_ids
            
            if not local_tool_id and should_install:
                try:
                    result = await _install_tool_internal(tool_id, project_id, api_key)
                    local_tool_id = result.get("id")
                except Exception as e:
                    logger.warning(f"Batch install: Failed to install tool {tool_id}: {str(e)}")
            
            # 如果有了本地 ID，加入绑定列表
            if local_tool_id:
                installed_tool_bindings.append({
                    "tool_id": local_tool_id,
                    "enabled": True
                })
    
    # 3.2 安装模型并获取提供商 ID
    associated_llm_provider_id = None
    if agent_template.model_id:
        # 先检查本地是否已有该商店模型的记录（且 Provider 也未删除）
        from app.models import AIModel, AIProvider
        existing_model = db.scalar(
            select(AIModel)
            .join(AIProvider, AIModel.provider_id == AIProvider.id)
            .where(AIModel.store_resource_id == agent_template.model_id)
            .where(AIModel.deleted_at.is_(None))
            .where(AIProvider.deleted_at.is_(None))
            .where(AIProvider.project_id == project_id)
        )
        
        # 如果需要安装或已存在
        if install_in.install_model or existing_model:
            try:
                # _install_model_internal 会处理同步并返回包含 provider 相关信息的字典
                # 但我们需要拿到数据库中的 provider 对象来获取它的 UUID
                await _install_model_internal(agent_template.model_id, project_id, api_key, db)
                
                # 重新查询获取 provider_id
                # 刚才的 internal helper 已经 commit 了，所以这里直接查最新的
                model_record = db.scalar(
                    select(AIModel)
                    .join(AIProvider, AIModel.provider_id == AIProvider.id)
                    .where(AIModel.store_resource_id == agent_template.model_id)
                    .where(AIModel.deleted_at.is_(None))
                    .where(AIProvider.deleted_at.is_(None))
                    .where(AIProvider.project_id == project_id)
                )
                if model_record:
                    associated_llm_provider_id = model_record.provider_id
            except Exception as e:
                logger.warning(f"Batch install: Failed to install/get model {agent_template.model_id}: {str(e)}")

    # 4. 调用 ai_client.create_agent() 创建本地 Agent
    try:
        agent_data = {
            "name": agent_template.title_zh or agent_template.name,
            "is_remote_store_agent": True,
            "remote_agent_url": f"{settings.STORE_SERVICE_URL.rstrip('/')}/api/v1/agentos",
            "store_agent_id": str(agent_template.id),
            "project_id": str(project_id),
            "instruction": agent_template.instruction_zh or agent_template.instruction,
            "model": agent_template.model.name if agent_template.model else "gpt-4o",
            "config": agent_template.default_config,
            "tools": installed_tool_bindings,  # 自动关联已安装的工具
            "llm_provider_id": str(associated_llm_provider_id) if associated_llm_provider_id else None  # 关联已安装的模型提供商
        }
        
        result = await ai_client.create_agent(
            project_id=str(project_id),
            agent_data=agent_data,
        )
        
        # 5. 记录商店安装
        try:
            await store_client.install_agent(install_in.resource_id, api_key)
        except Exception as e:
            logger.warning(f"Failed to record agent installation in store: {str(e)}")
            
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agent in AI service: {str(e)}"
        )


    return {"success": True}


@router.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_store_request(
    path: str,
    request: Request,
    current_user: Staff = Depends(get_current_active_user),
):
    """
    透明代理 Store API 请求，不解析参数，直接转发。
    支持 GET, POST, PUT, DELETE, PATCH 等方法。
    
    认证处理:
    - 如果请求头包含 X-Store-Authorization，则使用它作为商店的 Authorization 头
    - 否则移除 TGO 的 Authorization 头（商店不认识）
    """
    # 1. 构建目标 URL
    target_url = f"{settings.STORE_SERVICE_URL.rstrip('/')}/api/v1/{path}"
    if request.query_params:
        target_url = f"{target_url}?{request.query_params}"

    # 2. 准备请求头
    # 移除可能导致远程服务器 403 的头部
    excluded_headers = (
        "host", 
        "content-length", 
        "authorization", 
        "origin", 
        "referer", 
        "connection",
        "accept-encoding"
    )
    headers = {k: v for k, v in request.headers.items() if k.lower() not in excluded_headers}
    
    # 伪装浏览器 User-Agent，防止被 WAF 拦截
    headers["user-agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # 3. 处理商店认证
    # 如果前端传了 X-Store-Authorization，转换为 Authorization 头发给商店
    store_auth = request.headers.get("x-store-authorization")
    if store_auth:
        headers["authorization"] = store_auth
    
    # 4. 获取请求体
    body = await request.body()

    # 5. 发送请求
    async with httpx.AsyncClient(timeout=settings.STORE_TIMEOUT) as client:
        try:
            # 使用流式响应以处理大文件或保持性能
            # 注意：这里为了健壮性，不解析 body，直接转发
            proxy_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=True
            )
            
            # 5. 返回响应
            return Response(
                content=proxy_response.content,
                status_code=proxy_response.status_code,
                headers={k: v for k, v in proxy_response.headers.items() if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")}
            )
        except httpx.RequestError as e:
            logger.error(f"Store proxy connection error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to Store service: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Store proxy unexpected error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal error during Store proxy: {str(e)}"
            )


@router.get("/config")
async def get_store_config(
    current_user: Staff = Depends(get_current_active_user),
):
    """返回 Store 服务配置（Web URL 等）"""
    return {
        "store_web_url": settings.STORE_WEB_URL,
        "store_api_url": settings.STORE_SERVICE_URL,
    }
