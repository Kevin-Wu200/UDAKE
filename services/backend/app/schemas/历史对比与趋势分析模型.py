"""
历史对比与趋势分析模型
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"


class TimeSeriesRecord(BaseModel):
    """单条时间序列记录"""

    timestamp: datetime = Field(..., description="时间戳")
    value: float = Field(..., description="数值")
    point_id: Optional[str] = Field(default=None, description="点位ID")
    x: Optional[float] = Field(default=None, description="空间坐标X")
    y: Optional[float] = Field(default=None, description="空间坐标Y")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class SnapshotCreateRequest(BaseModel):
    """创建快照请求"""

    dataset_id: str = Field(..., min_length=1, description="数据集ID")
    version_label: Optional[str] = Field(default=None, description="版本标签")
    records: List[TimeSeriesRecord] = Field(..., min_length=1, description="快照数据")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="快照元数据")


class SnapshotMetadata(BaseModel):
    """快照元信息"""

    dataset_id: str
    version: int
    version_label: Optional[str] = None
    created_at: datetime
    record_count: int
    compressed: bool = True
    file_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SnapshotCreateResponse(BaseModel):
    """创建快照响应"""

    snapshot: SnapshotMetadata


class SnapshotListResponse(BaseModel):
    """快照列表响应"""

    dataset_id: str
    total_versions: int
    versions: List[SnapshotMetadata]


class VersionComparisonRequest(BaseModel):
    """版本对比请求"""

    dataset_id: str = Field(..., min_length=1)
    from_version: int = Field(..., ge=1)
    to_version: int = Field(..., ge=1)
    heatmap_grid_size: int = Field(default=16, ge=4, le=64)


class ValueDiffItem(BaseModel):
    """单点差值"""

    key: str
    from_value: Optional[float] = None
    to_value: Optional[float] = None
    absolute_diff: float
    relative_diff: Optional[float] = None
    timestamp: Optional[datetime] = None
    x: Optional[float] = None
    y: Optional[float] = None


class ComparisonSummary(BaseModel):
    """对比摘要"""

    total_points: int
    changed_points: int
    unchanged_points: int
    avg_absolute_diff: float
    max_absolute_diff: float
    min_absolute_diff: float


class HeatmapComparison(BaseModel):
    """热力图对比"""

    rows: int
    cols: int
    matrix: List[List[float]]


class VersionComparisonResponse(BaseModel):
    """版本对比响应"""

    dataset_id: str
    from_version: int
    to_version: int
    summary: ComparisonSummary
    diffs: List[ValueDiffItem]
    heatmap: HeatmapComparison


class MannKendallResult(BaseModel):
    """Mann-Kendall 检验结果"""

    tau: float
    s: float
    z: float
    p_value: float
    has_trend: bool


class LinearTrendResult(BaseModel):
    """线性趋势结果"""

    slope: float
    intercept: float
    r_squared: float
    direction: str


class PeriodicComponent(BaseModel):
    """周期分量"""

    frequency: float
    period: float
    amplitude: float


class AnomalyPoint(BaseModel):
    """异常点"""

    index: int
    timestamp: datetime
    value: float
    score: float
    anomaly_type: str


class ForecastPoint(BaseModel):
    """预测点"""

    index: int
    timestamp: datetime
    predicted_value: float
    lower_bound: float
    upper_bound: float


class ForecastEvaluation(BaseModel):
    """预测评估"""

    mae: float
    mape: float
    r2: float
    accuracy: float


class TrendAnalysisRequest(BaseModel):
    """趋势分析请求"""

    dataset_id: str = Field(..., min_length=1)
    version: Optional[int] = Field(default=None, ge=1)
    alpha: float = Field(default=0.05, gt=0, lt=1)
    forecast_horizon: int = Field(default=12, ge=1, le=365)
    seasonal_period: Optional[int] = Field(default=None, ge=2, le=365)
    anomaly_z_threshold: float = Field(default=2.5, ge=1.0, le=6.0)


class TrendAnalysisResponse(BaseModel):
    """趋势分析响应"""

    dataset_id: str
    version: int
    sample_size: int
    linear_trend: LinearTrendResult
    mann_kendall: MannKendallResult
    periodic_components: List[PeriodicComponent]
    anomalies: List[AnomalyPoint]
    forecast: List[ForecastPoint]
    evaluation: ForecastEvaluation


class HistoryReportRequest(BaseModel):
    """分析报告请求"""

    dataset_id: str = Field(..., min_length=1)
    from_version: int = Field(..., ge=1)
    to_version: int = Field(..., ge=1)
    forecast_horizon: int = Field(default=12, ge=1, le=365)


class HistoryReportResponse(BaseModel):
    """分析报告响应"""

    report_id: str
    dataset_id: str
    generated_at: datetime
    download_url: str
    comparison: VersionComparisonResponse
    trend: TrendAnalysisResponse


class HistoryExportRequest(BaseModel):
    """导出请求"""

    dataset_id: str = Field(..., min_length=1)
    format: ExportFormat = Field(default=ExportFormat.JSON)


class HistoryExportResponse(BaseModel):
    """导出响应"""

    dataset_id: str
    format: ExportFormat
    content: str


class HistoryImportRequest(BaseModel):
    """导入请求"""

    dataset_id: str = Field(..., min_length=1)
    format: ExportFormat = Field(default=ExportFormat.JSON)
    content: str = Field(..., min_length=1)
    version_label: Optional[str] = Field(default=None)


class HistoryImportResponse(BaseModel):
    """导入响应"""

    dataset_id: str
    imported_version: int
    imported_records: int


class ArchiveSnapshotsRequest(BaseModel):
    """归档请求"""

    dataset_id: str = Field(..., min_length=1)
    keep_latest: int = Field(default=20, ge=1, le=500)


class ArchiveSnapshotsResponse(BaseModel):
    """归档响应"""

    dataset_id: str
    archived_count: int
    kept_count: int
