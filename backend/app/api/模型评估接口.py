"""
模型评估报告接口
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

from ai_extension.模型评估报告生成 import ModelEvaluator

router = APIRouter()
evaluator = ModelEvaluator()

class ModelEvaluationRequest(BaseModel):
    """模型评估请求"""
    task_id: str = Field(..., description="任务ID")
    actual_values: List[float] = Field(..., description="实际值列表")
    predicted_values: List[float] = Field(..., description="预测值列表")
    variance: List[float] = Field(..., description="方差列表")
    model_params: Optional[Dict[str, Any]] = Field(default=None, description="模型参数")
    x_coords: Optional[List[float]] = Field(default=None, description="X坐标列表")
    y_coords: Optional[List[float]] = Field(default=None, description="Y坐标列表")

class ModelEvaluationResponse(BaseModel):
    """模型评估响应"""
    task_id: str
    report: Dict[str, Any]
    error_metrics: Dict[str, float]
    correlation: float
    quality_score: float
    sample_size: int
    recommendations: List[str]
    message: str

@router.post("/model/evaluation", response_model=ModelEvaluationResponse)
async def evaluate_model(request: ModelEvaluationRequest):
    """
    模型评估

    基于实际值和预测值生成模型评估报告，返回：
    - 误差指标（MAE、RMSE、MAPE）
    - 相关性分析
    - 方差统计
    - 综合质量分数
    - 改进建议
    """
    try:
        # 转换为numpy数组
        actual_values = np.array(request.actual_values)
        predicted_values = np.array(request.predicted_values)
        variance = np.array(request.variance)

        # 验证数据长度
        if len(actual_values) != len(predicted_values):
            raise HTTPException(
                status_code=400,
                detail="实际值和预测值数据长度不一致"
            )

        if len(actual_values) != len(variance):
            raise HTTPException(
                status_code=400,
                detail="实际值和方差数据长度不一致"
            )

        if len(actual_values) < 5:
            raise HTTPException(
                status_code=400,
                detail="数据点数量过少，至少需要5个点"
            )

        # 添加坐标信息到模型参数
        model_params = request.model_params or {}
        if request.x_coords and request.y_coords:
            model_params.update({
                "x_coords": request.x_coords,
                "y_coords": request.y_coords
            })

        # 生成评估报告
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, model_params
        )

        return ModelEvaluationResponse(
            task_id=request.task_id,
            report=report,
            error_metrics=report["error_metrics"],
            correlation=report["correlation"],
            quality_score=report["quality_score"],
            sample_size=report["sample_size"],
            recommendations=report["recommendations"],
            message="模型评估完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型评估失败: {str(e)}")