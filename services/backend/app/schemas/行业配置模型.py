"""
行业配置模型 - 不同行业的克里金插值预设参数
"""
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class Industry(str, Enum):
    """行业类型枚举"""
    MINING = "mining"  # 矿业
    GEOLOGY = "geology"  # 地质
    HYDROLOGY = "hydrology"  # 水文
    METEOROLOGY = "meteorology"  # 气象
    POLLUTION = "pollution"  # 污染
    SOIL = "soil"  # 土壤
    ENVIRONMENT = "environment"  # 环境
    TOPOGRAPHY = "topography"  # 地形测绘
    AGRICULTURE = "agriculture"  # 农业遥感
    URBAN_HEAT = "urban_heat"  # 城市热岛监测
    CUSTOM = "custom"  # 自定义

class IndustryConfig(BaseModel):
    """行业配置"""
    industry: Industry = Field(..., description="行业类型")
    name: str = Field(..., description="行业名称")
    description: str = Field(..., description="行业描述")
    default_method: str = Field(..., description="默认克里金方法")
    default_variogram: str = Field(..., description="默认变异函数模型")
    default_grid_resolution: int = Field(..., description="默认网格分辨率")
    default_nlags: int = Field(..., description="默认滞后数")
    enable_anisotropy: bool = Field(default=False, description="是否启用各向异性")
    enable_trend_detection: bool = Field(default=True, description="是否启用趋势检测")
    max_range: Optional[float] = Field(default=None, description="最大变程")
    nugget_ratio: Optional[float] = Field(default=None, description="块金比")
    custom_parameters: Dict[str, Any] = Field(default_factory=dict, description="自定义参数")
    template_filename: str = Field(..., description="模板文件名")

class IndustryListResponse(BaseModel):
    """行业列表响应"""
    industries: list[IndustryConfig]
    count: int

class IndustryRecommendationRequest(BaseModel):
    """基于行业的参数推荐请求"""
    data_id: str = Field(..., description="数据ID")
    industry: Industry = Field(..., description="行业类型")
    enable_cross_validation: bool = Field(default=True, description="是否启用交叉验证")

class IndustryRecommendationResponse(BaseModel):
    """基于行业的参数推荐响应"""
    industry: Industry
    industry_name: str
    recommended_method: str
    recommended_variogram: str
    recommended_grid_resolution: int
    recommended_nlags: int
    enable_anisotropy: bool
    enable_trend_detection: bool
    custom_parameters: Dict[str, Any]
    template_available: bool
    template_filename: str
    message: str
