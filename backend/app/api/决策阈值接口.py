"""
决策阈值分析接口
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

from uncertainty_dashboard.决策阈值分析 import DecisionThresholdAnalyzer

router = APIRouter()
analyzer = DecisionThresholdAnalyzer()

class DecisionThresholdRequest(BaseModel):
    """决策阈值分析请求"""
    task_id: str = Field(..., description="任务ID")
    prediction: List[List[float]] = Field(..., description="预测结果矩阵")
    variance: List[List[float]] = Field(..., description="方差数据矩阵")
    x_coords: List[float] = Field(..., description="X坐标列表")
    y_coords: List[float] = Field(..., description="Y坐标列表")
    decision_goal: str = Field(..., description="决策目标")
    custom_thresholds: Optional[List[float]] = Field(default=None, description="自定义阈值列表")
    risk_tolerance: float = Field(default=0.1, description="风险容忍度")

class DecisionThresholdResponse(BaseModel):
    """决策阈值分析响应"""
    task_id: str
    decision_goal: str
    threshold_analyses: Dict[str, Any]
    recommended_threshold: float
    risk_assessment: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    message: str

@router.post("/decision/thresholds", response_model=DecisionThresholdResponse)
async def analyze_decision_thresholds(request: DecisionThresholdRequest):
    """
    决策阈值分析

    基于预测结果和方差数据，分析不同决策阈值的效果，返回：
    - 各阈值分析结果
    - 推荐的最优阈值
    - 风险评估
    - 阈值建议列表
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

        # 生成默认阈值或使用自定义阈值
        if request.custom_thresholds:
            thresholds = request.custom_thresholds
        else:
            # 基于预测值分位数生成5个阈值
            percentiles = [20, 40, 50, 60, 80]
            thresholds = [float(np.percentile(prediction, p)) for p in percentiles]

        # 分析阈值
        threshold_analyses = analyzer.analyze_thresholds(
            prediction, variance, thresholds
        )

        # 推荐阈值
        recommended_threshold = threshold_analyses["recommended_threshold"]

        # 风险评估
        risk_assessment = analyzer.calculate_decision_risk(
            prediction, variance, recommended_threshold, request.risk_tolerance
        )

        # 生成阈值建议
        recommendations = analyzer.generate_threshold_recommendations(
            prediction, variance, n_thresholds=5
        )

        return DecisionThresholdResponse(
            task_id=request.task_id,
            decision_goal=request.decision_goal,
            threshold_analyses=threshold_analyses,
            recommended_threshold=recommended_threshold,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
            message="决策阈值分析完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"决策阈值分析失败: {str(e)}")