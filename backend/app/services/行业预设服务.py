"""
行业预设服务 - 管理不同行业的克里金插值预设参数
"""
from ..schemas.行业配置模型 import Industry, IndustryConfig
from ..schemas.插值参数模型 import VariogramModel, KrigingMethod
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class IndustryPresetService:
    """行业预设服务"""

    def __init__(self):
        self.INDUSTRY_CONFIGS = {
            Industry.MINING: IndustryConfig(
                industry=Industry.MINING,
                name="矿业",
                description="矿产勘探与评估，适合处理高值变化大、异常值多的数据",
                default_method=KrigingMethod.UNIVERSAL.value,
                default_variogram=VariogramModel.EXPONENTIAL.value,
                default_grid_resolution=150,
                default_nlags=12,
                enable_anisotropy=True,
                enable_trend_detection=True,
                max_range=5000,
                nugget_ratio=0.1,
                custom_parameters={
                    "min_points_per_sector": 5,
                    "max_search_radius": 10000
                },
                template_filename="mining_template.geojson"
            ),
            Industry.GEOLOGY: IndustryConfig(
                industry=Industry.GEOLOGY,
                name="地质",
                description="地质勘探，适合数据稀疏、空间相关性强的场景",
                default_method=KrigingMethod.ORDINARY.value,
                default_variogram=VariogramModel.SPHERICAL.value,
                default_grid_resolution=100,
                default_nlags=12,
                enable_anisotropy=True,
                enable_trend_detection=False,
                max_range=10000,
                nugget_ratio=0.05,
                custom_parameters={
                    "respect_fault_lines": True,
                    "stratification_enabled": False
                },
                template_filename="geology_template.geojson"
            ),
            Industry.HYDROLOGY: IndustryConfig(
                industry=Industry.HYDROLOGY,
                name="水文",
                description="水文地质调查，适合具有方向性趋势（沿河流）的数据",
                default_method=KrigingMethod.UNIVERSAL.value,
                default_variogram=VariogramModel.EXPONENTIAL.value,
                default_grid_resolution=120,
                default_nlags=10,
                enable_anisotropy=True,
                enable_trend_detection=True,
                max_range=3000,
                nugget_ratio=0.15,
                custom_parameters={
                    "flow_direction": None,
                    "elevation_correction": True
                },
                template_filename="hydrology_template.geojson"
            ),
            Industry.METEOROLOGY: IndustryConfig(
                industry=Industry.METEOROLOGY,
                name="气象",
                description="气象数据分析，适合数据密集、具有季节性变化的场景",
                default_method=KrigingMethod.UNIVERSAL.value,
                default_variogram=VariogramModel.GAUSSIAN.value,
                default_grid_resolution=200,
                default_nlags=15,
                enable_anisotropy=True,
                enable_trend_detection=True,
                max_range=50000,
                nugget_ratio=0.05,
                custom_parameters={
                    "elevation_factor": 0.0065,
                    "seasonal_adjustment": True
                },
                template_filename="meteorology_template.geojson"
            ),
            Industry.POLLUTION: IndustryConfig(
                industry=Industry.POLLUTION,
                name="污染",
                description="环境污染评估，适合局部异常、受污染源影响的数据",
                default_method=KrigingMethod.UNIVERSAL.value,
                default_variogram=VariogramModel.SPHERICAL.value,
                default_grid_resolution=100,
                default_nlags=10,
                enable_anisotropy=False,
                enable_trend_detection=True,
                max_range=2000,
                nugget_ratio=0.2,
                custom_parameters={
                    "source_point_influence": True,
                    "distance_decay": "inverse"
                },
                template_filename="pollution_template.geojson"
            ),
            Industry.SOIL: IndustryConfig(
                industry=Industry.SOIL,
                name="土壤",
                description="土壤调查，适合分布不均、受地形影响的数据",
                default_method=KrigingMethod.ORDINARY.value,
                default_variogram=VariogramModel.SPHERICAL.value,
                default_grid_resolution=80,
                default_nlags=12,
                enable_anisotropy=False,
                enable_trend_detection=False,
                max_range=2000,
                nugget_ratio=0.15,
                custom_parameters={
                    "slope_correction": True,
                    "soil_type_weighting": True
                },
                template_filename="soil_template.geojson"
            ),
            Industry.ENVIRONMENT: IndustryConfig(
                industry=Industry.ENVIRONMENT,
                name="环境",
                description="环境综合评估，适合多因素影响、不确定性大的数据",
                default_method=KrigingMethod.UNIVERSAL.value,
                default_variogram=VariogramModel.EXPONENTIAL.value,
                default_grid_resolution=120,
                default_nlags=12,
                enable_anisotropy=True,
                enable_trend_detection=True,
                max_range=3000,
                nugget_ratio=0.1,
                custom_parameters={
                    "multi_factor_weighting": True,
                    "uncertainty_quantification": True
                },
                template_filename="environment_template.geojson"
            ),
            Industry.TOPOGRAPHY: IndustryConfig(
                industry=Industry.TOPOGRAPHY,
                name="地形测绘",
                description="高精度地形测量与制图，适合DEM数据处理和等高线插值",
                default_method=KrigingMethod.UNIVERSAL.value,
                default_variogram=VariogramModel.GAUSSIAN.value,
                default_grid_resolution=200,
                default_nlags=15,
                enable_anisotropy=True,
                enable_trend_detection=True,
                max_range=10000,
                nugget_ratio=0.05,
                custom_parameters={
                    "elevation_correction": True,
                    "slope_analysis": True,
                    "aspect_correction": True,
                    "contour_generation": True
                },
                template_filename="topography_template.geojson"
            ),
            Industry.CUSTOM: IndustryConfig(
                industry=Industry.CUSTOM,
                name="自定义",
                description="自定义参数配置，由用户根据具体情况调整",
                default_method=KrigingMethod.ORDINARY.value,
                default_variogram=VariogramModel.SPHERICAL.value,
                default_grid_resolution=100,
                default_nlags=6,
                enable_anisotropy=False,
                enable_trend_detection=False,
                max_range=None,
                nugget_ratio=None,
                custom_parameters={},
                template_filename="custom_template.geojson"
            )
        }

    def get_industry_config(self, industry: Industry) -> IndustryConfig:
        """
        获取指定行业的配置

        Args:
            industry: 行业类型

        Returns:
            行业配置对象

        Raises:
            ValueError: 如果行业类型不存在
        """
        config = self.INDUSTRY_CONFIGS.get(industry)
        if not config:
            raise ValueError(f"不支持的行业类型: {industry}")
        return config

    def list_industries(self) -> List[IndustryConfig]:
        """
        获取所有行业配置列表

        Returns:
            行业配置列表
        """
        return list(self.INDUSTRY_CONFIGS.values())

    def get_industry_by_name(self, name: str) -> IndustryConfig:
        """
        根据行业名称获取配置

        Args:
            name: 行业名称

        Returns:
            行业配置对象

        Raises:
            ValueError: 如果行业名称不存在
        """
        for config in self.INDUSTRY_CONFIGS.values():
            if config.name == name:
                return config
        raise ValueError(f"不存在的行业名称: {name}")

    def validate_industry_parameters(
        self,
        industry: Industry,
        parameters: Dict[str, Any]
    ) -> bool:
        """
        验证行业参数是否有效

        Args:
            industry: 行业类型
            parameters: 参数字典

        Returns:
            是否有效
        """
        config = self.get_industry_config(industry)

        # 验证必需参数
        required_params = ["method", "variogram_model", "grid_resolution", "nlags"]
        for param in required_params:
            if param not in parameters:
                logger.warning(f"缺少必需参数: {param}")
                return False

        # 验证参数范围
        if parameters["grid_resolution"] < 10 or parameters["grid_resolution"] > 500:
            logger.warning(f"网格分辨率超出范围: {parameters['grid_resolution']}")
            return False

        if parameters["nlags"] < 3 or parameters["nlags"] > 30:
            logger.warning(f"滞后数超出范围: {parameters['nlags']}")
            return False

        return True