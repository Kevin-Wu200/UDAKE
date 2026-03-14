"""
误差预测接口
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

from ai_extension.误差预测模型 import ErrorPredictor

router = APIRouter()
predictor = ErrorPredictor()

class ErrorPredictRequest(BaseModel):
    """误差预测请求"""
    task_id: str = Field(..., description="任务ID")
    x_coords: List[float] = Field(..., description="X坐标列表")
    y_coords: List[float] = Field(..., description="Y坐标列表")
    predicted_values: List[float] = Field(..., description="预测值列表")
    actual_values: Optional[List[float]] = Field(default=None, description="实际值列表（用于训练）")
    train_model: bool = Field(default=False, description="是否训练模型")

class ErrorPredictResponse(BaseModel):
    """误差预测响应"""
    task_id: str
    predicted_errors: List[float]
    confidence_scores: List[float]
    statistics: Dict[str, float]
    training_results: Optional[Dict[str, Any]] = None
    message: str

@router.post("/error/predict", response_model=ErrorPredictResponse)
async def predict_errors(request: ErrorPredictRequest):
    """
    误差预测

    基于采样点位置和预测值预测插值误差，返回：
    - 预测误差分布
    - 置信度分数
    - 统计信息
    - 模型训练结果（如果训练）
    """
    try:
        # 转换为numpy数组
        x = np.array(request.x_coords)
        y = np.array(request.y_coords)
        predicted_values = np.array(request.predicted_values)

        # 验证数据长度
        if len(x) != len(y) or len(x) != len(predicted_values):
            raise HTTPException(
                status_code=400,
                detail="坐标和预测值数据长度不一致"
            )

        if len(x) < 10:
            raise HTTPException(
                status_code=400,
                detail="数据点数量过少，至少需要10个点"
            )

        training_results = None

        # 如果需要训练模型
        if request.train_model:
            if request.actual_values is None:
                raise HTTPException(
                    status_code=400,
                    detail="训练模型需要提供实际值"
                )

            actual_values = np.array(request.actual_values)

            if len(actual_values) != len(predicted_values):
                raise HTTPException(
                    status_code=400,
                    detail="实际值和预测值数据长度不一致"
                )

            # 训练模型
            training_results = predictor.train(
                x, y, actual_values, predicted_values
            )

        # 预测误差
        predicted_errors = predictor.predict_error(x, y, predicted_values)

        # 估计置信度
        confidence_scores = predictor.estimate_confidence(
            x, y, predicted_values
        )

        # 统计信息
        statistics = {
            "total_points": len(predicted_errors),
            "mean_error": float(np.mean(predicted_errors)),
            "std_error": float(np.std(predicted_errors)),
            "min_error": float(np.min(predicted_errors)),
            "max_error": float(np.max(predicted_errors)),
            "median_error": float(np.median(predicted_errors)),
            "mean_confidence": float(np.mean(confidence_scores))
        }

        return ErrorPredictResponse(
            task_id=request.task_id,
            predicted_errors=predicted_errors.tolist(),
            confidence_scores=confidence_scores.tolist(),
            statistics=statistics,
            training_results=training_results,
            message="误差预测完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"误差预测失败: {str(e)}")