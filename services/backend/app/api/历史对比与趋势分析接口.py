"""
历史对比与趋势分析接口
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.历史对比与趋势分析模型 import (
    ArchiveSnapshotsRequest,
    ArchiveSnapshotsResponse,
    HistoryExportRequest,
    HistoryExportResponse,
    HistoryImportRequest,
    HistoryImportResponse,
    HistoryReportRequest,
    HistoryReportResponse,
    SnapshotCreateRequest,
    SnapshotCreateResponse,
    SnapshotListResponse,
    TrendAnalysisRequest,
    TrendAnalysisResponse,
    VersionComparisonRequest,
    VersionComparisonResponse,
)
from ..services.历史对比与趋势分析服务 import history_comparison_trend_service

router = APIRouter()


@router.post("/history-analysis/snapshots", response_model=SnapshotCreateResponse)
async def create_snapshot(request: SnapshotCreateRequest):
    """创建历史快照"""
    try:
        snapshot = history_comparison_trend_service.create_snapshot(request)
        return SnapshotCreateResponse(snapshot=snapshot)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history-analysis/snapshots/{dataset_id}", response_model=SnapshotListResponse)
async def list_snapshots(dataset_id: str):
    """获取历史版本列表"""
    try:
        return history_comparison_trend_service.list_snapshots(dataset_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/history-analysis/snapshots/{dataset_id}/{version}")
async def delete_snapshot(dataset_id: str, version: int):
    """删除指定版本的历史快照"""
    try:
        history_comparison_trend_service.delete_snapshot(dataset_id, version)
        return {"message": "快照删除成功"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/history-analysis/compare", response_model=VersionComparisonResponse)
async def compare_versions(request: VersionComparisonRequest):
    """多版本差值对比 + 热力图矩阵"""
    try:
        return history_comparison_trend_service.compare_versions(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/history-analysis/trend", response_model=TrendAnalysisResponse)
async def analyze_trend(request: TrendAnalysisRequest):
    """趋势分析（Mann-Kendall、线性回归、周期、异常、预测）"""
    try:
        return history_comparison_trend_service.analyze_trend(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/history-analysis/report", response_model=HistoryReportResponse)
async def generate_report(request: HistoryReportRequest):
    """生成历史对比与趋势分析报告"""
    try:
        return history_comparison_trend_service.generate_report(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/history-analysis/export", response_model=HistoryExportResponse)
async def export_history(request: HistoryExportRequest):
    """导出历史数据（JSON/CSV）"""
    try:
        return history_comparison_trend_service.export_history(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/history-analysis/import", response_model=HistoryImportResponse)
async def import_history(request: HistoryImportRequest):
    """导入历史数据并创建新版本"""
    try:
        return history_comparison_trend_service.import_history(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/history-analysis/archive", response_model=ArchiveSnapshotsResponse)
async def archive_snapshots(request: ArchiveSnapshotsRequest):
    """归档旧版本快照"""
    try:
        return history_comparison_trend_service.archive_snapshots(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
