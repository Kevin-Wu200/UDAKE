"""
资源监控接口
"""
from typing import List

from fastapi import APIRouter, HTTPException

from ..schemas.资源监控模型 import (
    ResourceMonitoringConfig,
    ResourceOptimizationSuggestion,
    ResourceStatistics,
    ResourceType,
    ResourceWarning,
    SystemResources,
)
from ..services.资源监控服务 import resource_monitoring_service

router = APIRouter()

@router.get("/system/resources", response_model=SystemResources)
async def get_system_resources():
    """
    获取当前系统资源使用情况
    """
    try:
        resources = resource_monitoring_service.get_current_resources()
        return resources
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取资源信息失败: {str(e)}")

@router.get("/system/resources/statistics/{resource_type}", response_model=ResourceStatistics)
async def get_resource_statistics(
    resource_type: ResourceType,
    period_hours: int = 24
):
    """
    获取资源统计信息
    """
    try:
        statistics = resource_monitoring_service.get_resource_statistics(
            resource_type, period_hours
        )
        if not statistics:
            raise HTTPException(status_code=404, detail="没有可用的统计数据")
        return statistics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")

@router.get("/system/resources/warnings", response_model=List[ResourceWarning])
async def get_resource_warnings(limit: int = 10):
    """
    获取资源警告
    """
    try:
        warnings = resource_monitoring_service.get_warnings(limit)
        return warnings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取警告失败: {str(e)}")

@router.delete("/system/resources/warnings")
async def clear_resource_warnings():
    """
    清除资源警告
    """
    try:
        resource_monitoring_service.clear_warnings()
        return {"message": "警告已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除警告失败: {str(e)}")

@router.get("/system/resources/suggestions", response_model=List[ResourceOptimizationSuggestion])
async def get_resource_suggestions(limit: int = 10):
    """
    获取资源优化建议
    """
    try:
        suggestions = resource_monitoring_service.get_suggestions(limit)
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取建议失败: {str(e)}")

@router.delete("/system/resources/suggestions")
async def clear_resource_suggestions():
    """
    清除资源优化建议
    """
    try:
        resource_monitoring_service.clear_suggestions()
        return {"message": "建议已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除建议失败: {str(e)}")

@router.get("/system/resources/config", response_model=ResourceMonitoringConfig)
async def get_resource_config():
    """
    获取资源监控配置
    """
    try:
        config = resource_monitoring_service.get_config()
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")

@router.put("/system/resources/config")
async def update_resource_config(config: ResourceMonitoringConfig):
    """
    更新资源监控配置
    """
    try:
        resource_monitoring_service.update_config(config)
        return {"message": "配置已更新", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")

@router.post("/system/resources/monitoring/start")
async def start_monitoring():
    """
    启动资源监控
    """
    try:
        resource_monitoring_service.start_monitoring()
        return {"message": "资源监控已启动"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动监控失败: {str(e)}")

@router.post("/system/resources/monitoring/stop")
async def stop_monitoring():
    """
    停止资源监控
    """
    try:
        resource_monitoring_service.stop_monitoring()
        return {"message": "资源监控已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止监控失败: {str(e)}")
