"""
数据模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Point(BaseModel):
    """空间点"""
    x: float = Field(..., description="X坐标")
    y: float = Field(..., description="Y坐标")
    value: float = Field(..., description="观测值")

class SpatialData(BaseModel):
    """空间数据"""
    points: List[Point] = Field(..., description="采样点列表")
    crs: str = Field(default="EPSG:4326", description="坐标系")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")

class BoundingBox(BaseModel):
    """边界框"""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

class DataUploadResponse(BaseModel):
    """数据上传响应"""
    data_id: str
    point_count: int
    bounds: BoundingBox
    message: str
