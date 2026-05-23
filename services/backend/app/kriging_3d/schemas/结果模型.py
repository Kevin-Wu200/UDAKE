"""
3D克里金结果模型
"""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel


class TaskStatus3D(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Stats3D(BaseModel):
    """3D统计信息"""
    mean: float
    std: float
    min: float
    max: float
    median: float
    count: int


class VariogramResult3D(BaseModel):
    """3D变异函数结果"""
    model_config = {'protected_namespaces': ()}

    model_type: str
    nugget: float
    sill: float
    range_value: float
    r_squared: float
    lags: List[float]
    semivariance: List[float]
    fitted_values: List[float]


class CrossValidation3D(BaseModel):
    """3D交叉验证结果"""
    rmse: float
    mae: float
    r_squared: float
    mean_error: float
    residuals: Optional[List[float]] = None


class Kriging3DResult(BaseModel):
    """3D克里金结果"""
    task_id: str
    status: TaskStatus3D
    progress: float = 0.0
    grid_shape: Optional[List[int]] = None
    prediction_stats: Optional[Stats3D] = None
    variance_stats: Optional[Stats3D] = None
    variogram: Optional[VariogramResult3D] = None
    cross_validation: Optional[CrossValidation3D] = None
    result_path: Optional[str] = None
    error: Optional[str] = None


class SliceResult(BaseModel):
    """切片结果"""
    axis: str
    position: float
    grid_x: List[float]
    grid_y: List[float]
    values: List[List[float]]
    variance: Optional[List[List[float]]] = None
    stats: Optional[Stats3D] = None


class DataUploadResponse3D(BaseModel):
    """3D数据上传响应"""
    data_id: str
    point_count: int
    bounds: Dict[str, float]
    z_range: Dict[str, float]
    message: str
