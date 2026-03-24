"""
实时插值系统 FastAPI 路由
Real-time Interpolation System API Routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from .realtime_service import RealtimeInterpolationService, ServiceManager
from ..services import RealtimeSpatioTemporalService

# 创建服务管理器
service_manager = ServiceManager()
realtime_service = service_manager.create_service("default")
realtime_spatiotemporal_service = RealtimeSpatioTemporalService()

router = APIRouter()


# ==================== 数据模型 ====================

class CreateSubscriptionRequest(BaseModel):
    """创建订阅请求"""
    subscription_id: str
    data_type: str = "generic"
    spatial_extent: Dict[str, float]
    update_frequency: int = 5
    interpolation_params: Optional[Dict[str, Any]] = None
    notification_config: Optional[Dict[str, Any]] = None


class DataPointRequest(BaseModel):
    """数据点请求"""
    subscription_id: str
    point: Dict[str, Any]


class PredictionRequest(BaseModel):
    """预测请求"""
    subscription_id: str
    x: float
    y: float


class RealtimeSpatioTemporalTrainRequest(BaseModel):
    """realtime_interpolation 时空模型训练请求"""
    model_type: str = Field(default="st_transformer", description="st_transformer/gcn_lstm/convlstm/stgcn")
    coords: List[List[float]] = Field(default_factory=list, description="[[x, y], ...]")
    series: List[List[List[float]]] = Field(default_factory=list, description="[n_nodes, seq_len, n_features]")
    targets: Optional[List[List[float]]] = Field(default=None, description="[n_nodes, pred_horizon], 可选")
    epochs: int = Field(default=20, ge=5, le=300)
    pred_horizon: int = Field(default=6, ge=1, le=48)


class RealtimeSpatioTemporalPredictRequest(BaseModel):
    """realtime_interpolation 时空模型推理请求"""
    model_type: str = Field(default="st_transformer", description="st_transformer/gcn_lstm/convlstm/stgcn")
    coords: List[List[float]] = Field(default_factory=list, description="[[x, y], ...]")
    series: List[List[List[float]]] = Field(default_factory=list, description="[n_nodes, seq_len, n_features]")
    pred_horizon: int = Field(default=6, ge=1, le=48)
    fusion_strategy: str = Field(default="gating", description="concat/add/gating")
    uncertainty_method: Optional[str] = Field(default=None, description="mc_dropout/deep_ensemble/bayesian")
    enable_memory_optimization: bool = Field(default=True)
    enable_gpu_acceleration: bool = Field(default=False)
    enable_inference_acceleration: bool = Field(default=True)
    enable_long_sequence_optimization: bool = Field(default=False)
    long_sequence_chunk: int = Field(default=48, ge=8, le=512)


# ==================== 订阅管理接口 ====================

@router.post("/subscriptions")
async def create_subscription(request: CreateSubscriptionRequest):
    """
    创建订阅

    创建一个新的实时插值订阅，指定空间范围和插值参数。
    """
    try:
        subscription_data = {
            'subscription_id': request.subscription_id,
            'data_type': request.data_type,
            'spatial_extent': request.spatial_extent,
            'update_frequency': request.update_frequency,
            'interpolation_params': request.interpolation_params or {},
            'notification_config': request.notification_config or {}
        }

        result = realtime_service.create_subscription(subscription_data)

        if result['success']:
            return {
                'subscription_id': request.subscription_id,
                'status': 'created',
                'created_at': result.get('created_at', None)
            }
        else:
            raise HTTPException(status_code=400, detail=result['error'])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建订阅失败: {str(e)}")


@router.get("/subscriptions/{subscription_id}")
async def get_subscription(subscription_id: str):
    """
    获取订阅信息
    """
    try:
        if subscription_id not in realtime_service.subscriptions:
            raise HTTPException(status_code=404, detail="订阅不存在")

        kriging = realtime_service.subscriptions[subscription_id]
        subscription = kriging.subscription

        return {
            'subscription_id': subscription.subscription_id,
            'data_type': subscription.data_type,
            'spatial_extent': {
                'min_x': subscription.spatial_extent.min_x,
                'max_x': subscription.spatial_extent.max_x,
                'min_y': subscription.spatial_extent.min_y,
                'max_y': subscription.spatial_extent.max_y
            },
            'update_frequency': subscription.update_frequency,
            'interpolation_params': subscription.interpolation_params,
            'notification_config': subscription.notification_config,
            'created_at': subscription.created_at.isoformat() if subscription.created_at else None,
            'active': True
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取订阅失败: {str(e)}")


@router.get("/subscriptions")
async def list_subscriptions(active: Optional[bool] = None):
    """
    列出所有订阅
    """
    try:
        subscriptions = []

        for sub_id, kriging in realtime_service.subscriptions.items():
            subscription = kriging.subscription

            if active is None or (active and sub_id in realtime_service.subscriptions):
                subscriptions.append({
                    'subscription_id': sub_id,
                    'data_type': subscription.data_type,
                    'active': True
                })

        return {
            'subscriptions': subscriptions,
            'total': len(subscriptions)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出订阅失败: {str(e)}")


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str):
    """
    删除订阅
    """
    try:
        result = realtime_service.delete_subscription(subscription_id)

        if result['success']:
            return {
                'subscription_id': subscription_id,
                'status': 'deleted',
                'timestamp': None
            }
        else:
            raise HTTPException(status_code=404, detail=result['error'])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除订阅失败: {str(e)}")


# ==================== 增量更新接口 ====================

@router.post("/updates")
async def add_data_point(request: DataPointRequest):
    """
    添加数据点并触发增量更新
    """
    try:
        result = realtime_service.add_data_point(
            request.subscription_id,
            request.point
        )

        if result['success']:
            update_result = {
                'update_id': result['update_id'],
                'subscription_id': request.subscription_id,
                'timestamp': None,
                'update_type': 'incremental',
                'affected_region': result['affected_region'],
                'version': result.get('version', 0),
                'statistics': {
                    'update_time_ms': result.get('processing_time', 0) * 1000,
                    'affected_points': result.get('statistics', {}).get('affected_points', 0)
                }
            }
            return update_result
        else:
            raise HTTPException(status_code=400, detail=result['error'])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加数据点失败: {str(e)}")


@router.post("/subscriptions/{subscription_id}/data-points")
async def add_data_point_alias(subscription_id: str, point: Dict[str, Any]):
    """
    添加数据点并触发增量更新（前端兼容别名）
    """
    try:
        result = realtime_service.add_data_point(subscription_id, point)

        if result['success']:
            update_result = {
                'update_id': result['update_id'],
                'subscription_id': subscription_id,
                'timestamp': None,
                'update_type': 'incremental',
                'affected_region': result['affected_region'],
                'version': result.get('version', 0),
                'statistics': {
                    'update_time_ms': result.get('processing_time', 0) * 1000,
                    'affected_points': result.get('statistics', {}).get('affected_points', 0)
                }
            }
            return update_result
        else:
            raise HTTPException(status_code=400, detail=result['error'])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加数据点失败: {str(e)}")


# ==================== 查询接口 ====================

@router.get("/subscriptions/{subscription_id}/query")
async def query_point(subscription_id: str, x: float, y: float):
    """
    查询指定点的预测值
    """
    try:
        result = realtime_service.get_prediction(subscription_id, x, y)

        if result['success']:
            return {
                'x': x,
                'y': y,
                'prediction': result['prediction'],
                'variance': result['variance'],
                'confidence': result['confidence'],
                'version': None,
                'timestamp': None
            }
        else:
            raise HTTPException(status_code=404, detail=result['error'])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/subscriptions/{subscription_id}/prediction")
async def get_prediction_alias(subscription_id: str, x: float, y: float):
    """
    获取指定点的预测值（前端兼容别名）
    """
    try:
        result = realtime_service.get_prediction(subscription_id, x, y)

        if result['success']:
            return {
                'x': x,
                'y': y,
                'prediction': result['prediction'],
                'variance': result['variance'],
                'confidence': result['confidence'],
                'version': None,
                'timestamp': None
            }
        else:
            raise HTTPException(status_code=404, detail=result['error'])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预测失败: {str(e)}")


# ==================== 时空预测集成接口 ====================

@router.post("/realtime/spatiotemporal/train")
async def train_spatiotemporal(request: RealtimeSpatioTemporalTrainRequest):
    """
    在 realtime_interpolation 模块中训练时空预测模型。
    """
    try:
        return realtime_spatiotemporal_service.train(
            model_type=request.model_type,
            coords=request.coords,
            series=request.series,
            targets=request.targets,
            epochs=request.epochs,
            pred_horizon=request.pred_horizon,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"时空训练失败: {str(e)}")


@router.post("/realtime/spatiotemporal/predict")
async def predict_spatiotemporal(request: RealtimeSpatioTemporalPredictRequest):
    """
    在 realtime_interpolation 模块中执行时空预测。
    """
    try:
        return realtime_spatiotemporal_service.predict(
            model_type=request.model_type,
            coords=request.coords,
            series=request.series,
            pred_horizon=request.pred_horizon,
            fusion_strategy=request.fusion_strategy,
            uncertainty_method=request.uncertainty_method,
            enable_memory_optimization=request.enable_memory_optimization,
            enable_gpu_acceleration=request.enable_gpu_acceleration,
            enable_inference_acceleration=request.enable_inference_acceleration,
            enable_long_sequence_optimization=request.enable_long_sequence_optimization,
            long_sequence_chunk=request.long_sequence_chunk,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"时空预测失败: {str(e)}")


# ==================== 缓存管理接口 ====================

@router.get("/cache/statistics")
async def get_cache_statistics():
    """
    获取缓存统计信息
    """
    try:
        stats = realtime_service.get_stats()

        cache_stats = stats.get('cache', {})

        return {
            'l1_cache': {
                'size': cache_stats.get('l1_size', 0),
                'capacity': 1000,
                'hit_rate': cache_stats.get('l1_hit_rate', 0.0),
                'miss_rate': 1.0 - cache_stats.get('l1_hit_rate', 0.0)
            },
            'l2_cache': {
                'size': cache_stats.get('l2_size', 0),
                'capacity': 10000,
                'hit_rate': cache_stats.get('l2_hit_rate', 0.0),
                'miss_rate': 1.0 - cache_stats.get('l2_hit_rate', 0.0)
            },
            'overall': {
                'hit_rate': cache_stats.get('overall_hit_rate', 0.0),
                'miss_rate': 1.0 - cache_stats.get('overall_hit_rate', 0.0)
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {str(e)}")


@router.delete("/cache")
async def clear_cache(
    level: Optional[str] = None,
    subscription_id: Optional[str] = None
):
    """
    清除缓存
    """
    try:
        if realtime_service.cache_manager:
            if subscription_id:
                realtime_service.cache_manager.remove(f"sub_{subscription_id}")
            else:
                realtime_service.cache_manager.clear()

            return {
                'status': 'success',
                'cleared_entries': 1,
                'timestamp': None
            }
        else:
            return {
                'status': 'success',
                'cleared_entries': 0,
                'timestamp': None
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


# ==================== 状态监控接口 ====================

@router.get("/system/status")
async def get_system_status():
    """
    获取系统状态
    """
    try:
        health = realtime_service.health_check()
        stats = realtime_service.get_stats()

        return {
            'timestamp': None,
            'system_status': 'healthy' if health['healthy'] else 'error',
            'performance': {
                'avg_update_time_ms': stats['requests'].get('avg_processing_time', 0) * 1000,
                'max_update_time_ms': 0,
                'concurrent_updates': 0,
                'cache_hit_rate': stats.get('cache', {}).get('overall_hit_rate', 0.0),
                'memory_usage_gb': 0,
                'cpu_usage_percent': 0
            },
            'subscriptions': {
                'active': health['active_subscriptions'],
                'total_updates_today': stats['requests'].get('total_updates', 0)
            },
            'alerts': []
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")


@router.get("/system/metrics")
async def get_metrics(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    granularity: str = "hour"
):
    """
    获取性能指标
    """
    try:
        stats = realtime_service.get_stats()

        return {
            'metrics': [
                {
                    'timestamp': None,
                    'update_time_ms': stats['requests'].get('avg_processing_time', 0) * 1000,
                    'cache_hit_rate': stats.get('cache', {}).get('overall_hit_rate', 0.0),
                    'memory_usage_gb': 0
                }
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取性能指标失败: {str(e)}")


@router.get("/system/alerts")
async def get_alerts(
    level: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """
    获取告警列表
    """
    try:
        stats = realtime_service.get_stats()

        # 检查服务健康状况
        alerts = []

        if not realtime_service.healthy:
            alerts.append({
                'id': 'health_check',
                'level': 'critical',
                'message': '服务健康检查失败',
                'timestamp': None,
                'resolved': False
            })

        # 检查队列大小
        queue_size = stats['update_queue'].get('size', 0)
        if queue_size > 100:
            alerts.append({
                'id': 'queue_backlog',
                'level': 'warning',
                'message': f'更新队列积压: {queue_size} 个任务',
                'timestamp': None,
                'resolved': False
            })

        return {
            'alerts': alerts,
            'total': len(alerts)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取告警列表失败: {str(e)}")
