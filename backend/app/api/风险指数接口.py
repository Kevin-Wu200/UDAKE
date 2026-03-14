"""
风险指数计算接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import numpy as np
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from uncertainty_dashboard.风险指数计算 import RiskIndexCalculator

router = APIRouter()
calculator = RiskIndexCalculator()

class RiskCalculateRequest(BaseModel):
    """风险指数计算请求"""
    task_id: str = Field(..., description="任务ID")
    prediction: List[List[float]] = Field(..., description="预测结果矩阵")
    variance: List[List[float]] = Field(..., description="方差数据矩阵")
    x_coords: List[float] = Field(..., description="X坐标列表")
    y_coords: List[float] = Field(..., description="Y坐标列表")
    confidence_level: float = Field(default=0.95, description="置信度")
    threshold_values: Optional[Dict[str, float]] = Field(default=None, description="阈值配置")

class RiskCalculateResponse(BaseModel):
    """风险指数计算响应"""
    task_id: str
    risk_index: List[List[float]]
    statistics: Dict[str, float]
    risk_levels: Dict[str, int]
    high_risk_area: int
    high_risk_percentage: float
    risk_rating: str
    message: str

@router.post("/risk/calculate", response_model=RiskCalculateResponse)
async def calculate_risk(request: RiskCalculateRequest):
    """
    风险指数计算

    基于预测值和方差数据计算风险指数，返回：
    - 风险指数矩阵
    - 统计信息
    - 风险等级分布
    - 高风险区域统计
    """
    try:
        # 转换为numpy数组
        variance = np.array(request.variance)
        prediction = np.array(request.prediction)
        x_coords = np.array(request.x_coords)
        y_coords = np.array(request.y_coords)

        # 验证数据形状
        if variance.shape != prediction.shape:
            raise HTTPException(
                status_code=400,
                detail="预测结果和方差数据形状不匹配"
            )

        if len(x_coords) != variance.shape[1] or len(y_coords) != variance.shape[0]:
            raise HTTPException(
                status_code=400,
                detail="坐标与数据形状不匹配"
            )

        # 计算空间风险
        spatial_risk = calculator.calculate_spatial_risk(
            variance, prediction, x_coords, y_coords
        )

        # 确定风险评级
        high_risk_pct = spatial_risk["high_risk_percentage"]
        if high_risk_pct > 30:
            risk_rating = "高风险"
        elif high_risk_pct > 15:
            risk_rating = "中等风险"
        else:
            risk_rating = "低风险"

        return RiskCalculateResponse(
            task_id=request.task_id,
            risk_index=spatial_risk["risk_index"].tolist(),
            statistics=spatial_risk["statistics"],
            risk_levels=spatial_risk["risk_levels"],
            high_risk_area=spatial_risk["high_risk_area"],
            high_risk_percentage=spatial_risk["high_risk_percentage"],
            risk_rating=risk_rating,
            message="风险指数计算完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风险指数计算失败: {str(e)}")