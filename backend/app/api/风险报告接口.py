"""
空间风险报告生成接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import numpy as np
import sys
from pathlib import Path
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from uncertainty_dashboard.空间风险报告生成 import SpatialRiskReporter

router = APIRouter()
reporter = SpatialRiskReporter()

class RiskReportRequest(BaseModel):
    """风险报告生成请求"""
    task_id: str = Field(..., description="任务ID")
    prediction: List[List[float]] = Field(..., description="预测结果矩阵")
    variance: List[List[float]] = Field(..., description="方差数据矩阵")
    risk_index: List[List[float]] = Field(..., description="风险指数矩阵")
    x_coords: List[float] = Field(..., description="X坐标列表")
    y_coords: List[float] = Field(..., description="Y坐标列表")
    uncertainty_levels: Optional[Dict[str, Any]] = Field(default=None, description="不确定性等级信息")
    threshold_analysis: Optional[Dict[str, Any]] = Field(default=None, description="阈值分析结果")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")
    save_to_file: bool = Field(default=True, description="是否保存到文件")

class RiskReportResponse(BaseModel):
    """风险报告生成响应"""
    task_id: str
    report: Dict[str, Any]
    report_id: str
    generated_at: str
    file_path: Optional[str] = None
    message: str

@router.post("/risk/report", response_model=RiskReportResponse)
async def generate_risk_report(request: RiskReportRequest):
    """
    空间风险报告生成

    基于预测结果、方差数据和风险指数生成完整的空间风险报告，返回：
    - 执行摘要
    - 风险评估
    - 阈值分析
    - 空间统计信息
    - 建议
    """
    try:
        # 转换为numpy数组
        variance = np.array(request.variance)
        prediction = np.array(request.prediction)
        risk_index = np.array(request.risk_index)
        x_coords = np.array(request.x_coords)
        y_coords = np.array(request.y_coords)

        # 验证数据形状
        if variance.shape != prediction.shape:
            raise HTTPException(
                status_code=400,
                detail="预测结果和方差数据形状不匹配"
            )

        if variance.shape != risk_index.shape:
            raise HTTPException(
                status_code=400,
                detail="预测结果和风险指数形状不匹配"
            )

        if len(x_coords) != variance.shape[1] or len(y_coords) != variance.shape[0]:
            raise HTTPException(
                status_code=400,
                detail="坐标与数据形状不匹配"
            )

        # 添加坐标信息到元数据
        metadata = request.metadata or {}
        metadata.update({
            "x_coords": x_coords.tolist(),
            "y_coords": y_coords.tolist(),
            "grid_shape": prediction.shape
        })

        # 生成报告
        report = reporter.generate_risk_report(
            task_id=request.task_id,
            prediction=prediction,
            variance=variance,
            risk_index=risk_index,
            uncertainty_levels=request.uncertainty_levels or {},
            threshold_analysis=request.threshold_analysis or {},
            metadata=metadata
        )

        # 保存到文件
        file_path = None
        if request.save_to_file:
            results_dir = Path(__file__).parent.parent / "结果文件"
            file_path = results_dir / f"risk_report_{request.task_id}.json"
            reporter.save_report(report, file_path)
            file_path = str(file_path)

        return RiskReportResponse(
            task_id=request.task_id,
            report=report,
            report_id=report["report_id"],
            generated_at=report["generated_at"],
            file_path=file_path,
            message="风险报告生成完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风险报告生成失败: {str(e)}")