"""
配置管理接口
提供应用配置信息给前端
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel

router = APIRouter(prefix="/api/config", tags=["配置管理"])

class ConfigResponse(BaseModel):
    """配置响应模型"""
    success: bool
    config: Dict[str, Any]

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
        "arcgis": {
            "apiKey": settings.ARCGIS_API_KEY,
            "portalUrl": settings.ARCGIS_PORTAL_URL,
            "env": settings.ARCGIS_ENV,
            "defaultBasemap": settings.ARCGIS_DEFAULT_BASEMAP,
            "defaultCenter": settings.arcgis_center_list,
            "defaultZoom": settings.ARCGIS_DEFAULT_ZOOM,
            "isMock": settings.ARCGIS_API_KEY == "YOUR_ARCGIS_API_KEY_HERE"
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
            "arcgis": {
                "apiKey": settings.ARCGIS_API_KEY,
                "portalUrl": settings.ARCGIS_PORTAL_URL,
                "env": settings.ARCGIS_ENV,
                "defaultBasemap": settings.ARCGIS_DEFAULT_BASEMAP,
                "defaultCenter": settings.arcgis_center_list,
                "defaultZoom": settings.ARCGIS_DEFAULT_ZOOM,
                "isMock": settings.ARCGIS_API_KEY == "YOUR_ARCGIS_API_KEY_HERE"
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