"""
输出结果模型
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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
    shapefile_url: Optional[str] = None
    statistics: Dict[str, float]

class VarianceResult(BaseModel):
    """方差结果"""
    task_id: str
    geotiff_url: Optional[str] = None
    geojson_url: Optional[str] = None
    shapefile_url: Optional[str] = None
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

class SamplingRecommendation(BaseModel):
    """采样建议点"""
    id: int = Field(..., description="采样点ID")
    x: float = Field(..., description="X坐标（经度）")
    y: float = Field(..., description="Y坐标（纬度）")
    variance: float = Field(..., description="预测方差")
    priority: str = Field(..., description="优先级：high/medium/low")
    uncertainty_level: int = Field(..., ge=1, le=5, description="不确定性等级：1-5")
    region_id: Optional[int] = Field(None, description="所属不确定性区域ID")
    distance_to_nearest: float = Field(..., description="距离最近采样点的距离")
    sampling_reason: str = Field(..., description="采样理由")
    expected_benefit: float = Field(..., description="预期收益（方差减少量）")
    confidence_score: Optional[float] = Field(None, description="该点置信度分数")

class SamplingRecommendationsResponse(BaseModel):
    """采样建议响应"""
    task_id: str
    strategy: str = Field(..., description="采样策略：variance_based/spatial_coverage/hybrid")
    n_recommendations: int = Field(..., description="建议点数量")
    recommendations: List[SamplingRecommendation] = Field(..., description="建议点列表")
    statistics: Dict[str, Any] = Field(..., description="统计信息")
    generated_at: datetime = Field(default_factory=datetime.now)
    confidence_score: Optional[float] = Field(None, description="整体置信度分数")
    confidence_threshold: Optional[float] = Field(None, description="行业置信度阈值")
    is_confidence_sufficient: Optional[bool] = Field(None, description="置信度是否达标")
    industry: Optional[str] = Field(None, description="行业类型")
