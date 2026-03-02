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
    method: KrigingMethod = Field(default=KrigingMethod.ORDINARY, description="克里金方法")
    variogram_model: VariogramModel = Field(default=VariogramModel.SPHERICAL, description="变异函数模型")
    grid_resolution: int = Field(default=100, description="网格分辨率")
    nlags: int = Field(default=6, description="滞后数")
    enable_cross_validation: bool = Field(default=True, description="是否启用交叉验证")
    n_folds: int = Field(default=5, description="交叉验证折数")

class TaskStartResponse(BaseModel):
    """任务启动响应"""
    task_id: str
    status: str
    message: str
