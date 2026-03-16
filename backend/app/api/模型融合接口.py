"""
模型融合API接口
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

from ..model_fusion.services.fusion_service import fusion_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ModelInput(BaseModel):
    """模型输入"""
    model_id: str
    model_name: str
    predictions: List[float]
    variances: Optional[List[float]] = None
    confidence_intervals: Optional[List[Dict[str, float]]] = None


class FusionConfigInput(BaseModel):
    """融合配置输入"""
    strategy: str = "weighted_average"
    weight_method: str = "rmse_based"
    min_weight: float = 0.0
    max_weight: float = 1.0
    normalize: bool = True
    smoothing: bool = False
    smoothing_factor: float = 0.1
    enable_cross_validation: bool = True
    enable_stability_check: bool = True
    enable_uncertainty_propagation: bool = True
    n_folds: int = 5


class CreateFusionTaskRequest(BaseModel):
    """创建融合任务请求"""
    models: List[ModelInput]
    config: FusionConfigInput
    true_values: Optional[List[float]] = None


class CompareStrategiesRequest(BaseModel):
    """比较策略请求"""
    models: List[ModelInput]
    config: FusionConfigInput
    true_values: Optional[List[float]] = None
    strategies: Optional[List[str]] = None


class OptimizeWeightsRequest(BaseModel):
    """优化权重请求"""
    models: List[ModelInput]
    config: FusionConfigInput
    true_values: List[float]


@router.post("/fusion/create-task")
async def create_fusion_task(request: CreateFusionTaskRequest):
    """
    创建模型融合任务

    - **models**: 模型预测列表
    - **config**: 融合配置
    - **true_values**: 真实值（可选，用于评估）
    """
    try:
        models_data = [m.dict() for m in request.models]
        config_data = request.config.dict()

        task_id = fusion_service.create_fusion_task(
            models=models_data,
            config=config_data,
            true_values=request.true_values
        )

        return {
            "success": True,
            "task_id": task_id,
            "message": "融合任务创建成功"
        }

    except Exception as e:
        logger.error(f"创建融合任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get("/fusion/task/{task_id}/status")
async def get_fusion_task_status(task_id: str):
    """
    获取融合任务状态
    """
    try:
        status = fusion_service.get_task_status(task_id)

        if status is None:
            raise HTTPException(status_code=404, detail="任务不存在")

        return {
            "success": True,
            "status": status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.get("/fusion/task/{task_id}/result")
async def get_fusion_task_result(task_id: str):
    """
    获取融合任务结果
    """
    try:
        result = fusion_service.get_task_result(task_id)

        if result is None:
            # 任务可能还在执行中
            status = fusion_service.get_task_status(task_id)
            if status and status['status'] == 'running':
                return {
                    "success": True,
                    "message": "任务正在执行中",
                    "status": "running"
                }
            else:
                raise HTTPException(status_code=404, detail="任务结果不存在")

        return {
            "success": True,
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取结果失败: {str(e)}")


@router.post("/fusion/compare-strategies")
async def compare_strategies(request: CompareStrategiesRequest):
    """
    比较不同融合策略

    - **models**: 模型预测列表
    - **config**: 融合配置
    - **true_values**: 真实值（可选）
    - **strategies**: 要比较的策略列表
    """
    try:
        models_data = [m.dict() for m in request.models]
        config_data = request.config.dict()

        task_id = fusion_service.compare_strategies(
            models=models_data,
            config=config_data,
            true_values=request.true_values,
            strategies=request.strategies
        )

        return {
            "success": True,
            "task_id": task_id,
            "message": "策略比较任务创建成功"
        }

    except Exception as e:
        logger.error(f"创建策略比较任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.post("/fusion/optimize-weights")
async def optimize_weights(request: OptimizeWeightsRequest):
    """
    优化权重计算方法

    - **models**: 模型预测列表
    - **config**: 融合配置
    - **true_values**: 真实值
    """
    try:
        models_data = [m.dict() for m in request.models]
        config_data = request.config.dict()

        task_id = fusion_service.optimize_weights(
            models=models_data,
            config=config_data,
            true_values=request.true_values
        )

        return {
            "success": True,
            "task_id": task_id,
            "message": "权重优化任务创建成功"
        }

    except Exception as e:
        logger.error(f"创建权重优化任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get("/fusion/tasks")
async def list_fusion_tasks():
    """
    列出所有融合任务
    """
    try:
        tasks = fusion_service.list_tasks()

        return {
            "success": True,
            "tasks": tasks,
            "total": len(tasks)
        }

    except Exception as e:
        logger.error(f"列出任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出任务失败: {str(e)}")


@router.get("/fusion/strategies")
async def list_fusion_strategies():
    """
    列出所有可用的融合策略
    """
    try:
        from ..model_fusion.core.fusion_models import FusionStrategy

        strategies = [
            {
                "value": strategy.value,
                "name": strategy.name,
                "description": _get_strategy_description(strategy)
            }
            for strategy in FusionStrategy
        ]

        return {
            "success": True,
            "strategies": strategies
        }

    except Exception as e:
        logger.error(f"列出策略失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出策略失败: {str(e)}")


@router.get("/fusion/weight-methods")
async def list_weight_methods():
    """
    列出所有可用的权重计算方法
    """
    try:
        from ..model_fusion.core.fusion_models import WeightMethod

        methods = [
            {
                "value": method.value,
                "name": method.name,
                "description": _get_weight_method_description(method)
            }
            for method in WeightMethod
        ]

        return {
            "success": True,
            "methods": methods
        }

    except Exception as e:
        logger.error(f"列出权重方法失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出权重方法失败: {str(e)}")


def _get_strategy_description(strategy: Any) -> str:
    """获取策略描述"""
    descriptions = {
        "simple_average": "简单平均融合",
        "weighted_average": "加权平均融合",
        "median": "中位数融合",
        "stacking": "堆叠融合（元学习）",
        "bayesian_model_average": "贝叶斯模型平均",
        "variance_weighted": "方差加权融合",
        "max_min": "最大最小融合（鲁棒）"
    }
    return descriptions.get(strategy.value, strategy.value)


def _get_weight_method_description(method: Any) -> str:
    """获取权重方法描述"""
    descriptions = {
        "equal": "等权重",
        "rmse_based": "基于RMSE的权重",
        "mae_based": "基于MAE的权重",
        "r2_based": "基于R²的权重",
        "cross_validation": "交叉验证权重",
        "bma": "贝叶斯模型平均权重",
        "uncertainty_based": "基于不确定性的权重",
        "adaptive": "自适应权重"
    }
    return descriptions.get(method.value, method.value)