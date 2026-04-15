"""
配置管理接口
提供应用配置信息给前端
"""
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..runtime_config_manager import get_runtime_config_manager

router = APIRouter(prefix="/api/config", tags=["配置管理"])

_RUNTIME_CONFIG_PATH = str(Path(__file__).resolve().parents[3] / "configs" / "validation_config.yaml")

class ConfigResponse(BaseModel):
    """配置响应模型"""
    success: bool
    config: Dict[str, Any]


class RuntimeConfigUpdateRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    actor: str = "api"
    comment: str = ""


class RuntimeConfigRollbackRequest(BaseModel):
    version: int
    actor: str = "api"

@router.get("/map", response_model=ConfigResponse)
async def get_map_config():
    """
    获取地图引擎配置
    
    返回所有地图引擎的API密钥和配置信息
    前端根据需要选择使用哪个地图引擎
    """
    from ..config import settings
    
    # 返回地图配置，但不暴露敏感信息
    config = {
        "geoscene": {
            "apiKey": settings.GEOSCENE_API_KEY,
            "portalUrl": settings.GEOSCENE_PORTAL_URL,
            "env": settings.GEOSCENE_ENV,
            "defaultBasemap": settings.GEOSCENE_DEFAULT_BASEMAP,
            "defaultCenter": settings.geoscene_center_list,
            "defaultZoom": settings.GEOSCENE_DEFAULT_ZOOM,
            "isMock": settings.geoscene_is_mock
        },
        "amap": {
            "apiKey": settings.AMAP_API_KEY,
            "securityCode": settings.AMAP_SECURITY_CODE,
            "defaultCenter": [119.72170376, 30.26262781],  # 杭州
            "defaultZoom": 18
        },
        "tianditu": {
            "apiKey": settings.TIANDITU_API_KEY,
            "token": settings.TIANDITU_TOKEN
        }
    }
    
    return ConfigResponse(success=True, config=config)

@router.get("/app", response_model=ConfigResponse)
async def get_app_config():
    """
    获取应用配置
    
    返回应用的基本配置信息
    """
    from ..config import settings
    
    config = {
        "appName": settings.APP_NAME,
        "version": settings.VERSION,
        "debug": settings.DEBUG,
        "corsOrigins": settings.cors_origins_list,
        "maxFileSize": settings.MAX_FILE_SIZE_MB,
        "maxConcurrentTasks": settings.MAX_CONCURRENT_TASKS,
        "taskTimeout": settings.TASK_TIMEOUT
    }
    
    return ConfigResponse(success=True, config=config)

@router.get("/ai", response_model=ConfigResponse)
async def get_ai_config():
    """
    获取AI扩展模块配置
    
    返回AI相关的配置信息
    """
    from ..config import settings
    
    config = {
        "cacheEnabled": settings.AI_CACHE_ENABLED,
        "maxBatchSize": settings.AI_MAX_BATCH_SIZE,
        "modelPath": settings.AI_MODEL_PATH
    }
    
    return ConfigResponse(success=True, config=config)

@router.get("/all", response_model=ConfigResponse)
async def get_all_config():
    """
    获取所有配置
    
    返回所有可公开的配置信息
    """
    from ..config import settings
    
    config = {
        "app": {
            "appName": settings.APP_NAME,
            "version": settings.VERSION,
            "debug": settings.DEBUG
        },
        "map": {
            "geoscene": {
                "apiKey": settings.GEOSCENE_API_KEY,
                "portalUrl": settings.GEOSCENE_PORTAL_URL,
                "env": settings.GEOSCENE_ENV,
                "defaultBasemap": settings.GEOSCENE_DEFAULT_BASEMAP,
                "defaultCenter": settings.geoscene_center_list,
                "defaultZoom": settings.GEOSCENE_DEFAULT_ZOOM,
                "isMock": settings.geoscene_is_mock
            },
            "amap": {
                "apiKey": settings.AMAP_API_KEY,
                "securityCode": settings.AMAP_SECURITY_CODE,
                "defaultCenter": [119.72170376, 30.26262781],
                "defaultZoom": 18
            },
            "tianditu": {
                "apiKey": settings.TIANDITU_API_KEY,
                "token": settings.TIANDITU_TOKEN
            }
        },
        "ai": {
            "cacheEnabled": settings.AI_CACHE_ENABLED,
            "maxBatchSize": settings.AI_MAX_BATCH_SIZE,
            "modelPath": settings.AI_MODEL_PATH
        },
        "limits": {
            "maxFileSize": settings.MAX_FILE_SIZE_MB,
            "maxConcurrentTasks": settings.MAX_CONCURRENT_TASKS,
            "taskTimeout": settings.TASK_TIMEOUT
        }
    }
    
    return ConfigResponse(success=True, config=config)


@router.get("/runtime/current")
async def get_runtime_current_config():
    manager = get_runtime_config_manager(_RUNTIME_CONFIG_PATH)
    return {"success": True, "data": manager.current()}


@router.get("/runtime/history")
async def get_runtime_config_history(limit: int = 20):
    manager = get_runtime_config_manager(_RUNTIME_CONFIG_PATH)
    items = manager.history(limit=limit)
    return {"success": True, "data": {"items": items, "count": len(items)}}


@router.post("/runtime/update")
async def update_runtime_config(payload: RuntimeConfigUpdateRequest):
    manager = get_runtime_config_manager(_RUNTIME_CONFIG_PATH)
    try:
        result = manager.update(payload.payload, actor=payload.actor, comment=payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "message": "运行时配置更新成功", "data": result}


@router.post("/runtime/rollback")
async def rollback_runtime_config(payload: RuntimeConfigRollbackRequest):
    manager = get_runtime_config_manager(_RUNTIME_CONFIG_PATH)
    try:
        result = manager.rollback(payload.version, actor=payload.actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "message": "运行时配置回滚成功", "data": result}


@router.get("/runtime/diff")
async def diff_runtime_config(from_version: int, to_version: int):
    manager = get_runtime_config_manager(_RUNTIME_CONFIG_PATH)
    try:
        result = manager.diff(from_version, to_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": result}


@router.post("/runtime/reload-check")
async def runtime_reload_check(actor: Optional[str] = "api"):
    manager = get_runtime_config_manager(_RUNTIME_CONFIG_PATH)
    result = manager.check_reload(actor=str(actor or "api"))
    return {"success": True, "data": result}
