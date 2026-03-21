"""
性能报告接口
"""
from fastapi import APIRouter, HTTPException
from ..schemas.性能报告模型 import (
    PerformanceReportRequest, PerformanceReportResponse,
    PerformanceTrendAnalysis, HistoricalPerformanceStats
)
from ..services.性能报告服务 import performance_report_service
from typing import Optional

router = APIRouter()

@router.post("/performance/report", response_model=PerformanceReportResponse)
async def generate_performance_report(request: PerformanceReportRequest):
    """
    生成性能报告
    """
    try:
        response = performance_report_service.generate_report(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/trend/{task_id}", response_model=PerformanceTrendAnalysis)
async def get_performance_trend(task_id: str, period_days: int = 30):
    """
    获取性能趋势分析
    """
    try:
        trend = performance_report_service.get_trend_analysis(task_id, period_days)
        if not trend:
            raise HTTPException(status_code=404, detail="无法获取趋势分析")
        return trend
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/historical-stats/{task_type}", response_model=HistoricalPerformanceStats)
async def get_historical_stats(task_type: str, period_days: int = 30):
    """
    获取历史统计
    """
    try:
        stats = performance_report_service.get_historical_stats(task_type, period_days)
        if not stats:
            raise HTTPException(status_code=404, detail="无法获取历史统计")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))