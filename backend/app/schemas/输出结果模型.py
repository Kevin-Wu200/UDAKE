"""
输出结果模型
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: TaskStatus
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None

class PredictionResult(BaseModel):
    """预测结果"""
    task_id: str
    geotiff_url: Optional[str] = None
    geojson_url: Optional[str] = None
    statistics: Dict[str, float]

class VarianceResult(BaseModel):
    """方差结果"""
    task_id: str
    geotiff_url: Optional[str] = None
    geojson_url: Optional[str] = None
    statistics: Dict[str, float]

class CrossValidationMetrics(BaseModel):
    """交叉验证指标"""
    rmse: float
    mae: float
    r2: float
    mse: float

class KrigingReport(BaseModel):
    """克里金报告"""
    task_id: str
    method: str
    variogram_model: str
    point_count: int
    grid_resolution: int
    cross_validation: Optional[CrossValidationMetrics] = None
    prediction_stats: Dict[str, float]
    variance_stats: Dict[str, float]
    execution_time: float
    generated_at: datetime
