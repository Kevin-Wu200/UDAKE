"""
插值参数模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class VariogramModel(str, Enum):
    """变异函数模型"""
    SPHERICAL = "spherical"
    EXPONENTIAL = "exponential"
    GAUSSIAN = "gaussian"
    LINEAR = "linear"

class KrigingMethod(str, Enum):
    """克里金方法"""
    ORDINARY = "ordinary"
    UNIVERSAL = "universal"
    BLOCK = "block"

class KrigingParameters(BaseModel):
    """克里金参数"""
    data_id: str = Field(..., description="数据ID")
    industry: Optional[str] = Field(default=None, description="行业类型（mining, geology, hydrology, meteorology, pollution, soil, environment, custom）")
    method: KrigingMethod = Field(default=KrigingMethod.ORDINARY, description="克里金方法")
    variogram_model: VariogramModel = Field(default=VariogramModel.SPHERICAL, description="变异函数模型")
    grid_resolution: int = Field(default=100, description="网格分辨率")
    nlags: int = Field(default=6, description="滞后数")
    enable_cross_validation: bool = Field(default=True, description="是否启用交叉验证")
    n_folds: int = Field(default=5, description="交叉验证折数")
    enable_anisotropy: bool = Field(default=False, description="是否启用各向异性")
    max_range: Optional[float] = Field(default=None, description="最大变程")
    nugget_ratio: Optional[float] = Field(default=None, description="块金比")

class TaskStartResponse(BaseModel):
    """任务启动响应"""
    task_id: str
    status: str
    message: str
