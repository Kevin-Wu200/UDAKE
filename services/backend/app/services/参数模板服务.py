"""
参数模板服务
"""
from ..schemas.批量处理模型 import (
    ParameterTemplate, ParameterTemplateListResponse,
    ParameterTemplateSaveRequest, ParameterValidationResult
)
from ..schemas.插值参数模型 import KrigingParameters
from ..services.数据预处理服务 import DataPreprocessor
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class ParameterTemplateService:
    """参数模板服务"""

    def __init__(self):
        self.templates_dir = Path(__file__).parent.parent.parent / "参数模板"
        self.templates_dir.mkdir(exist_ok=True)
        self.preprocessor = DataPreprocessor()
        self._initialize_default_templates()

    def _initialize_default_templates(self):
        """初始化默认参数模板"""
        default_templates = [
            {
                "name": "环境监测模板",
                "description": "适用于环境监测数据的克里金插值参数",
                "industry": "environment",
                "parameters": {
                    "method": "ordinary",
                    "variogram_model": "spherical",
                    "grid_resolution": 100,
                    "nlags": 6,
                    "enable_cross_validation": True,
                    "n_folds": 5,
                    "enable_anisotropy": False,
                    "max_range": None,
                    "nugget_ratio": None
                }
            },
            {
                "name": "农业采样模板",
                "description": "适用于农业土壤采样数据的克里金插值参数",
                "industry": "agriculture",
                "parameters": {
                    "method": "ordinary",
                    "variogram_model": "exponential",
                    "grid_resolution": 150,
                    "nlags": 8,
                    "enable_cross_validation": True,
                    "n_folds": 5,
                    "enable_anisotropy": True,
                    "max_range": None,
                    "nugget_ratio": 0.1
                }
            },
            {
                "name": "地质勘探模板",
                "description": "适用于地质勘探数据的克里金插值参数",
                "industry": "geology",
                "parameters": {
                    "method": "ordinary",
                    "variogram_model": "gaussian",
                    "grid_resolution": 80,
                    "nlags": 10,
                    "enable_cross_validation": True,
                    "n_folds": 5,
                    "enable_anisotropy": True,
                    "max_range": None,
                    "nugget_ratio": 0.2
                }
            },
            {
                "name": "水文监测模板",
                "description": "适用于水文监测数据的克里金插值参数",
                "industry": "hydrology",
                "parameters": {
                    "method": "ordinary",
                    "variogram_model": "spherical",
                    "grid_resolution": 120,
                    "nlags": 7,
                    "enable_cross_validation": True,
                    "n_folds": 5,
                    "enable_anisotropy": False,
                    "max_range": None,
                    "nugget_ratio": None
                }
            },
            {
                "name": "气象监测模板",
                "description": "适用于气象监测数据的克里金插值参数",
                "industry": "meteorology",
                "parameters": {
                    "method": "universal",
                    "variogram_model": "spherical",
                    "grid_resolution": 200,
                    "nlags": 12,
                    "enable_cross_validation": True,
                    "n_folds": 5,
                    "enable_anisotropy": True,
                    "max_range": None,
                    "nugget_ratio": None
                }
            }
        ]

        for template_data in default_templates:
            template_file = self.templates_dir / f"{template_data['name']}.json"
            if not template_file.exists():
                self._save_template_file(template_data)

    def _save_template_file(self, template_data: Dict[str, Any]):
        """保存模板文件"""
        template_file = self.templates_dir / f"{template_data['name']}.json"
        with open(template_file, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)

    def _load_template_file(self, template_file: Path) -> Optional[Dict[str, Any]]:
        """加载模板文件"""
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载模板文件失败: {template_file}, 错误: {str(e)}")
            return None

    def save_template(self, request: ParameterTemplateSaveRequest) -> ParameterTemplate:
        """保存参数模板"""
        try:
            template_id = str(hash(f"{request.name}_{datetime.now().timestamp()}"))
            template_data = {
                "template_id": template_id,
                "name": request.name,
                "description": request.description,
                "industry": request.industry,
                "parameters": request.parameters.model_dump(),
                "created_at": datetime.now().isoformat()
            }

            # 保存到文件
            self._save_template_file(template_data)

            return ParameterTemplate(**template_data)

        except Exception as e:
            logger.error(f"保存参数模板失败: {str(e)}")
            raise e

    def load_template(self, template_id: str) -> Optional[ParameterTemplate]:
        """加载参数模板"""
        try:
            # 查找模板文件
            for template_file in self.templates_dir.glob("*.json"):
                template_data = self._load_template_file(template_file)
                if template_data and template_data.get("template_id") == template_id:
                    return ParameterTemplate(**template_data)

            return None

        except Exception as e:
            logger.error(f"加载参数模板失败: {str(e)}")
            raise e

    def get_all_templates(self) -> ParameterTemplateListResponse:
        """获取所有参数模板"""
        try:
            templates = []
            for template_file in self.templates_dir.glob("*.json"):
                template_data = self._load_template_file(template_file)
                if template_data:
                    templates.append(ParameterTemplate(**template_data))

            return ParameterTemplateListResponse(
                templates=templates,
                total=len(templates)
            )

        except Exception as e:
            logger.error(f"获取所有参数模板失败: {str(e)}")
            raise e

    def delete_template(self, template_id: str) -> bool:
        """删除参数模板"""
        try:
            # 查找并删除模板文件
            for template_file in self.templates_dir.glob("*.json"):
                template_data = self._load_template_file(template_file)
                if template_data and template_data.get("template_id") == template_id:
                    template_file.unlink()
                    return True

            return False

        except Exception as e:
            logger.error(f"删除参数模板失败: {str(e)}")
            raise e

    def validate_parameters(self, parameters: KrigingParameters) -> ParameterValidationResult:
        """验证参数合理性"""
        errors = []
        warnings = []
        suggestions = []

        # 验证网格分辨率
        if parameters.grid_resolution < 10:
            errors.append("网格分辨率不能小于10")
        elif parameters.grid_resolution > 500:
            warnings.append("网格分辨率过大可能导致计算时间过长")

        # 验证滞后数
        if parameters.nlags < 3:
            errors.append("滞后数不能小于3")
        elif parameters.nlags > 20:
            warnings.append("滞后数过大可能导致过拟合")

        # 验证交叉验证折数
        if parameters.n_folds < 2:
            errors.append("交叉验证折数不能小于2")
        elif parameters.n_folds > 10:
            warnings.append("交叉验证折数过大可能导致验证不稳定")

        # 验证块金比
        if parameters.nugget_ratio is not None:
            if parameters.nugget_ratio < 0:
                errors.append("块金比不能为负数")
            elif parameters.nugget_ratio > 1:
                errors.append("块金比不能大于1")
            elif parameters.nugget_ratio > 0.5:
                warnings.append("块金比过大可能表示数据空间相关性较弱")

        # 验证最大变程
        if parameters.max_range is not None and parameters.max_range <= 0:
            errors.append("最大变程必须大于0")

        # 提供建议
        if parameters.enable_anisotropy and not parameters.max_range:
            suggestions.append("启用各向异性时建议设置最大变程")

        if not errors and not warnings:
            return ParameterValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                suggestions=suggestions
            )

        return ParameterValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )

    def auto_adjust_parameters(
        self,
        parameters: KrigingParameters,
        data_id: str
    ) -> KrigingParameters:
        """根据数据自动调整参数"""
        try:
            # 加载数据
            spatial_data = self.preprocessor.load_data(data_id)
            point_count = len(spatial_data.points)

            # 根据数据点数量调整网格分辨率
            if point_count < 50:
                parameters.grid_resolution = min(parameters.grid_resolution, 50)
            elif point_count < 100:
                parameters.grid_resolution = min(parameters.grid_resolution, 80)
            elif point_count < 500:
                parameters.grid_resolution = min(parameters.grid_resolution, 150)
            else:
                parameters.grid_resolution = min(parameters.grid_resolution, 200)

            # 根据数据点数量调整滞后数
            if point_count < 30:
                parameters.nlags = min(parameters.nlags, 4)
            elif point_count < 100:
                parameters.nlags = min(parameters.nlags, 6)
            elif point_count < 300:
                parameters.nlags = min(parameters.nlags, 8)
            else:
                parameters.nlags = min(parameters.nlags, 12)

            logger.info(f"根据数据自动调整参数: data_id={data_id}, point_count={point_count}")

            return parameters

        except Exception as e:
            logger.error(f"自动调整参数失败: {str(e)}")
            return parameters

    def apply_parameters_to_datasets(
        self,
        parameters: Optional[KrigingParameters],
        individual_parameters: Optional[Dict[str, KrigingParameters]],
        data_ids: List[str],
        auto_adjust: bool = True
    ) -> Dict[str, KrigingParameters]:
        """将参数应用到多个数据集"""
        result = {}

        for data_id in data_ids:
            # 确定使用哪个参数
            if individual_parameters and data_id in individual_parameters:
                params = individual_parameters[data_id]
            elif parameters:
                params = parameters
            else:
                # 如果没有提供参数，使用默认参数
                params = KrigingParameters(data_id=data_id)

            # 自动调整参数
            if auto_adjust:
                params = self.auto_adjust_parameters(params, data_id)

            result[data_id] = params

        return result

    def get_template_by_name(self, name: str) -> Optional[ParameterTemplate]:
        """根据名称获取参数模板"""
        try:
            template_file = self.templates_dir / f"{name}.json"
            if template_file.exists():
                template_data = self._load_template_file(template_file)
                if template_data:
                    return ParameterTemplate(**template_data)

            return None

        except Exception as e:
            logger.error(f"根据名称获取参数模板失败: {str(e)}")
            return None