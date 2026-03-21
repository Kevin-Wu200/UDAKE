"""
3D克里金参数模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class VariogramModel3D(str, Enum):
    """3D变异函数模型"""
    SPHERICAL = "spherical"
    EXPONENTIAL = "exponential"
    GAUSSIAN = "gaussian"
    LINEAR = "linear"


class KrigingMethod3D(str, Enum):
    """3D克里金方法"""
    ORDINARY = "ordinary"
    UNIVERSAL = "universal"
    INDICATOR = "indicator"


class AnisotropyParams(BaseModel):
    """各向异性参数"""
    ratio_xy: float = Field(default=1.0, description="XY平面各向异性比")
    ratio_xz: float = Field(default=1.0, description="XZ平面各向异性比")
    angle_xy: float = Field(default=0.0, description="XY平面旋转角度（度）")
    angle_xz: float = Field(default=0.0, description="XZ平面旋转角度（度）")
    angle_yz: float = Field(default=0.0, description="YZ平面旋转角度（度）")


class KrigingParameters3D(BaseModel):
    """3D克里金参数"""
    data_id: str = Field(..., description="数据ID")
    method: KrigingMethod3D = Field(default=KrigingMethod3D.ORDINARY, description="克里金方法")
    variogram_model: VariogramModel3D = Field(default=VariogramModel3D.SPHERICAL, description="变异函数模型")
    grid_resolution_x: int = Field(default=50, description="X方向网格分辨率")
    grid_resolution_y: int = Field(default=50, description="Y方向网格分辨率")
    grid_resolution_z: int = Field(default=20, description="Z方向网格分辨率")
    nlags: int = Field(default=12, description="滞后数")
    enable_cross_validation: bool = Field(default=True, description="是否启用交叉验证")
    n_folds: int = Field(default=5, description="交叉验证折数")
    enable_anisotropy: bool = Field(default=False, description="是否启用各向异性")
    anisotropy: Optional[AnisotropyParams] = Field(default=None, description="各向异性参数")
    max_range: Optional[float] = Field(default=None, description="最大变程")
    nugget_ratio: Optional[float] = Field(default=None, description="块金比")
    indicator_threshold: Optional[float] = Field(default=None, description="指示克里金阈值")
    block_size: Optional[int] = Field(default=None, description="分块大小（点数）")
    n_closest: int = Field(default=16, description="搜索最近邻点数")
    drift_terms: Optional[List[str]] = Field(default=None, description="漂移项（泛克里金）")


class SliceParams(BaseModel):
    """切片参数"""
    axis: str = Field(..., description="切片轴（x/y/z）")
    position: float = Field(..., description="切片位置")
    resolution: int = Field(default=100, description="切片分辨率")


class TaskStartResponse3D(BaseModel):
    """3D任务启动响应"""
    task_id: str
    status: str
    message: str
    grid_shape: Optional[List[int]] = None
