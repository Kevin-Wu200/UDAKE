"""
行业配置接口 - 提供行业配置查询和基于行业的参数推荐
"""
from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from ..schemas.行业配置模型 import (
    Industry,
    IndustryConfig,
    IndustryListResponse,
    IndustryRecommendationRequest,
    IndustryRecommendationResponse
)
from ..services.行业预设服务 import IndustryPresetService
from ..services.数据预处理服务 import DataPreprocessor
from ..services.模型选择服务 import ModelSelector
from pydantic import BaseModel
from typing import Dict, Any
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
industry_service = IndustryPresetService()
preprocessor = DataPreprocessor()
model_selector = ModelSelector()

# 模板文件路径
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')


@router.get("/industries", response_model=IndustryListResponse)
async def list_industries():
    """
    获取所有行业配置列表

    返回支持的所有行业类型及其配置信息
    """
    try:
        industries = industry_service.list_industries()
        return IndustryListResponse(
            industries=industries,
            count=len(industries)
        )
    except Exception as e:
        logger.error(f"获取行业列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取行业列表失败: {str(e)}")


@router.get("/industries/{industry}", response_model=IndustryConfig)
async def get_industry_config(industry: Industry):
    """
    获取指定行业的配置

    Args:
        industry: 行业类型
    """
    try:
        config = industry_service.get_industry_config(industry)
        return config
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取行业配置失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取行业配置失败: {str(e)}")


@router.post("/recommend-by-industry", response_model=IndustryRecommendationResponse)
async def recommend_by_industry(request: IndustryRecommendationRequest):
    """
    基于行业推荐插值参数

    结合行业预设配置和数据特征，提供优化的克里金参数推荐

    Args:
        request: 行业推荐请求
    """
    try:
        # 获取行业配置
        industry_config = industry_service.get_industry_config(request.industry)
        config_dict = industry_config.model_dump()

        # 加载数据
        spatial_data = preprocessor.load_data(request.data_id)

        # 提取坐标和值
        x = np.array([p.x for p in spatial_data.points])
        y = np.array([p.y for p in spatial_data.points])
        values = np.array([p.value for p in spatial_data.points])

        # 基于行业选择参数
        params = model_selector.select_parameters_by_industry(
            industry_config=config_dict,
            x=x,
            y=y,
            values=values,
            enable_cross_validation=request.enable_cross_validation
        )

        # 检查模板文件是否存在
        template_path = os.path.join(TEMPLATE_DIR, industry_config.template_filename)
        template_available = os.path.exists(template_path)

        return IndustryRecommendationResponse(
            industry=request.industry,
            industry_name=industry_config.name,
            recommended_method=params["method"].value,
            recommended_variogram=params["variogram_model"].value,
            recommended_grid_resolution=params["grid_resolution"],
            recommended_nlags=params["nlags"],
            enable_anisotropy=params.get("enable_anisotropy", False),
            enable_trend_detection=params.get("has_trend", False),
            custom_parameters=params.get("custom_parameters", {}),
            template_available=template_available,
            template_filename=industry_config.template_filename,
            message=f"基于 {industry_config.name} 行业的参数推荐完成"
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"参数推荐失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"参数推荐失败: {str(e)}")


@router.get("/templates/{template_name}")
async def download_template(template_name: str):
    """
    下载行业模板文件

    Args:
        template_name: 模板文件名
    """
    try:
        # 安全检查：确保模板名称在白名单中
        valid_templates = [
            "mining_template.geojson",
            "geology_template.geojson",
            "hydrology_template.geojson",
            "meteorology_template.geojson",
            "pollution_template.geojson",
            "soil_template.geojson",
            "environment_template.geojson",
            "topography_template.geojson",
            "custom_template.geojson"
        ]

        if template_name not in valid_templates:
            raise HTTPException(status_code=400, detail="无效的模板文件名")

        template_path = os.path.join(TEMPLATE_DIR, template_name)

        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail=f"模板文件不存在: {template_name}")

        return FileResponse(
            path=template_path,
            filename=template_name,
            media_type='application/json'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载模板失败: {str(e)}")


@router.get("/templates")
async def list_templates():
    """
    获取所有可用的模板文件列表
    """
    try:
        if not os.path.exists(TEMPLATE_DIR):
            return {"templates": [], "count": 0}

        templates = []
        for filename in os.listdir(TEMPLATE_DIR):
            if filename.endswith('.geojson') or filename.endswith('.json'):
                template_path = os.path.join(TEMPLATE_DIR, filename)
                templates.append({
                    "filename": filename,
                    "size": os.path.getsize(template_path),
                    "exists": True
                })

        return {"templates": templates, "count": len(templates)}

    except Exception as e:
        logger.error(f"获取模板列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模板列表失败: {str(e)}")