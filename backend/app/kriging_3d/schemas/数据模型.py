"""
3D克里金数据模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class Point3D(BaseModel):
    """三维空间点"""
    x: float = Field(..., description="X坐标")
    y: float = Field(..., description="Y坐标")
    z: float = Field(..., description="Z坐标（深度/高度）")
    value: float = Field(..., description="观测值")
    label: Optional[str] = Field(default=None, description="点标签")


class SpatialData3D(BaseModel):
    """三维空间数据"""
    points: List[Point3D] = Field(..., description="三维采样点列表")
    crs: str = Field(default="EPSG:4326", description="坐标系")
    z_unit: str = Field(default="m", description="Z轴单位（m/km/ft）")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class BoundingBox3D(BaseModel):
    """三维边界框"""
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float


class Grid3D(BaseModel):
    """三维网格配置"""
    nx: int = Field(default=50, description="X方向网格数")
    ny: int = Field(default=50, description="Y方向网格数")
    nz: int = Field(default=20, description="Z方向网格数")
