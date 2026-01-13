from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
    StoreBindRequest
)
from app.schemas.tools import ToolCreateRequest, ToolType as CoreToolType, ToolSourceType
from app.utils.crypto import encrypt_str, decrypt_str
from app.services.store_client import store_client
from app.services.ai_client import ai_client

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

    # 2. 调用商店 API 获取工具详情
    try:
        tool_detail = await store_client.get_tool(install_in.resource_id, api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch tool from Store: {str(e)}"
        )

    # 3. 构造本地工具创建请求
    tool_create = ToolCreateRequest(
        name=tool_detail["name"],
        title=tool_detail.get("title") or tool_detail.get("title_zh") or tool_detail["name"],
        title_zh=tool_detail.get("title_zh"),
        title_en=tool_detail.get("title_en"),
        description=tool_detail.get("description_zh") or tool_detail.get("description"),
        tool_type=CoreToolType.MCP,
        transport_type="http",
        endpoint=f"{settings.STORE_SERVICE_URL.rstrip('/')}/api/v1/execute/mcp/{install_in.resource_id}",
        tool_source_type=ToolSourceType.STORE,
        store_resource_id=install_in.resource_id,
        config=tool_detail.get("config", {})
    )

    # 4. 在 tgo-ai 创建 ai_tools 记录
    try:
        tool_data_dict = tool_create.model_dump(exclude_none=True)
        tool_data_dict["project_id"] = str(project_id)
        
        result = await ai_client.create_tool(tool_data=tool_data_dict)
        
        # 记录商店安装
        await store_client.install_tool(install_in.resource_id, api_key)
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tool in AI service: {str(e)}"
        )


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

    # 2. 调用商店 API 获取模型详情
    try:
        model_detail = await store_client.get_model(install_in.resource_id, api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch model from Store: {str(e)}"
        )

    # 3. 确保本地有一个 "Store" 类型的 LLMProvider
    # 这里我们为每个项目创建一个专用的 Store Provider
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
            api_base_url=f"{settings.STORE_SERVICE_URL.rstrip('/')}/api/v1/execute",
            api_key=encrypt_str(api_key), # 加密存储商店 API Key
            is_active=True,
            default_model=local_model_id,
        )
        db.add(provider)
    else:
        if not provider.default_model:
            provider.default_model = local_model_id
            db.add(provider)
    
    db.flush() # 确保 provider 已在数据库中

    # 4. 创建本地模型记录 (关联到 Provider)
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
            provider="openai_compatible", # 对应 AIProvider.provider
            model_id=local_model_id,
            model_name=model_detail.title_zh or model_detail.name,
            model_type=model_detail.model_type,
            description=model_detail.description_zh,
            is_active=True,
            capabilities=model_detail.config.get("capabilities", {}) if model_detail.config else {}
        )
        db.add(existing_model)
    else:
        # 更新已存在模型的元数据
        existing_model.model_name = model_detail.title_zh or model_detail.name
        existing_model.model_type = model_detail.model_type
        existing_model.description = model_detail.description_zh
        existing_model.capabilities = model_detail.config.get("capabilities", {}) if model_detail.config else {}
        db.add(existing_model)
    
    # 记录商店安装
    try:
        await store_client.install_model(install_in.resource_id, api_key)
    except Exception as e:
        logger.warning(f"Failed to record installation in store: {str(e)}")
    
    db.commit()
    return {"success": True, "model_id": local_model_id, "provider": provider_name}


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

    db.commit()
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
