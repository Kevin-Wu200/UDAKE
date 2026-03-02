"""
模型推荐接口 - 自动参数推荐
"""
from fastapi import APIRouter, HTTPException
from ..schemas.数据模型 import SpatialData
from ..services.数据预处理服务 import DataPreprocessor
from ..services.模型选择服务 import ModelSelector
from pydantic import BaseModel
from typing import Dict, Any
import numpy as np

router = APIRouter()
preprocessor = DataPreprocessor()
model_selector = ModelSelector()

class ModelRecommendationRequest(BaseModel):
    """模型推荐请求"""
    data_id: str
    enable_auto_model: bool = True

class ModelRecommendationResponse(BaseModel):
    """模型推荐响应"""
    recommended_variogram_model: str
    recommended_method: str
    recommended_grid_resolution: int
    recommended_nlags: int
    has_trend: bool
    model_scores: Dict[str, float]
    point_count: int
    message: str

@router.post("/recommend-parameters", response_model=ModelRecommendationResponse)
async def recommend_parameters(request: ModelRecommendationRequest):
    """
    自动推荐插值参数

    基于数据特征和交叉验证自动选择：
    - 最优变异函数模型（球状、指数、高斯、线性）
    - 克里金方法（普通、泛克里金、分块）
    - 网格分辨率
    - 滞后数
    """
    try:
        # 加载数据
        spatial_data = preprocessor.load_data(request.data_id)

        # 提取坐标和值
        x = np.array([p.x for p in spatial_data.points])
        y = np.array([p.y for p in spatial_data.points])
        values = np.array([p.value for p in spatial_data.points])

        # 自动选择参数
        params = model_selector.auto_select_parameters(
            x, y, values,
            enable_auto_model=request.enable_auto_model
        )

        return ModelRecommendationResponse(
            recommended_variogram_model=params["variogram_model"].value,
            recommended_method=params["method"].value,
            recommended_grid_resolution=params["grid_resolution"],
            recommended_nlags=params["nlags"],
            has_trend=params["has_trend"],
            model_scores=params["model_scores"],
            point_count=params["point_count"],
            message="参数推荐完成"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"参数推荐失败: {str(e)}")
