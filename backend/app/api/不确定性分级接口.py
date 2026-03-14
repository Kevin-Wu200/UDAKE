"""
不确定性分级接口
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

from uncertainty_dashboard.不确定性分级模型 import UncertaintyClassifier

router = APIRouter()
classifier = UncertaintyClassifier()

class UncertaintyClassifyRequest(BaseModel):
    """不确定性分级请求"""
    task_id: str = Field(..., description="任务ID")
    prediction: List[List[float]] = Field(..., description="预测结果矩阵")
    variance: List[List[float]] = Field(..., description="方差数据矩阵")
    x_coords: List[float] = Field(..., description="X坐标列表")
    y_coords: List[float] = Field(..., description="Y坐标列表")
    custom_thresholds: Optional[Dict[str, float]] = Field(default=None, description="自定义阈值")

class UncertaintyClassifyResponse(BaseModel):
    """不确定性分级响应"""
    task_id: str
    statistics: Dict[str, Dict[str, Any]]
    color_map: Dict[int, str]
    critical_zones: List[Dict[str, Any]]
    message: str

@router.post("/uncertainty/classify", response_model=UncertaintyClassifyResponse)
async def classify_uncertainty(request: UncertaintyClassifyRequest):
    """
    不确定性分级

    对预测结果和方差数据进行不确定性分级，返回：
    - 各等级统计信息
    - 颜色映射
    - 关键区域识别
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

        # 设置自定义阈值
        if request.custom_thresholds:
            classifier.thresholds.update(request.custom_thresholds)

        # 获取统计信息
        statistics = classifier.get_level_statistics(variance)

        # 生成不确定性地图
        uncertainty_map = classifier.generate_uncertainty_map(
            variance, x_coords, y_coords
        )

        # 识别关键区域
        critical_zones = classifier.identify_critical_zones(
            variance, x_coords, y_coords, critical_level=3
        )

        return UncertaintyClassifyResponse(
            task_id=request.task_id,
            statistics=statistics,
            color_map=uncertainty_map["color_map"],
            critical_zones=critical_zones[:100],  # 限制返回数量
            message="不确定性分级完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"不确定性分级失败: {str(e)}")