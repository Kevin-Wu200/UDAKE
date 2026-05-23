"""
性能报告模型
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReportFormat(str, Enum):
    """报告格式"""
    PDF = "pdf"
    HTML = "html"
    JSON = "json"

class StagePerformance(BaseModel):
    """阶段性能数据"""
    stage_name: str = Field(..., description="阶段名称")
    duration: float = Field(..., description="持续时间（秒）")
    start_time: datetime
    end_time: datetime
    memory_peak: float = Field(default=0.0, description="内存峰值（MB）")
    cpu_avg: float = Field(default=0.0, description="平均CPU使用率")
    cpu_peak: float = Field(default=0.0, description="峰值CPU使用率")

class TaskPerformanceData(BaseModel):
    """任务性能数据"""
    task_id: str
    task_type: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration: Optional[float] = Field(default=None, description="总耗时（秒）")
    stages: List[StagePerformance] = Field(default_factory=list, description="各阶段性能")
    memory_usage: Dict[str, float] = Field(default_factory=dict, description="内存使用情况")
    cpu_usage: Dict[str, float] = Field(default_factory=dict, description="CPU使用情况")
    disk_usage: float = Field(default=0.0, description="磁盘使用量（MB）")
    network_usage: Optional[Dict[str, float]] = Field(default=None, description="网络使用情况")
    data_size: Optional[int] = Field(default=None, description="数据大小（字节）")
    point_count: Optional[int] = Field(default=None, description="采样点数量")
    grid_resolution: Optional[int] = Field(default=None, description="网格分辨率")

class PerformanceMetrics(BaseModel):
    """性能指标"""
    total_execution_time: float = Field(..., description="总执行时间（秒）")
    avg_cpu_usage: float = Field(..., description="平均CPU使用率")
    max_cpu_usage: float = Field(..., description="最大CPU使用率")
    avg_memory_usage: float = Field(..., description="平均内存使用量（MB）")
    max_memory_usage: float = Field(..., description="最大内存使用量（MB）")
    total_disk_io: float = Field(default=0.0, description="总磁盘IO（MB）")
    throughput: float = Field(default=0.0, description="吞吐量（点/秒）")

class PerformanceBottleneck(BaseModel):
    """性能瓶颈"""
    bottleneck_type: str = Field(..., description="瓶颈类型：cpu/memory/disk/io")
    stage: str = Field(..., description="相关阶段")
    severity: str = Field(..., description="严重程度：low/medium/high/critical")
    description: str = Field(..., description="描述")
    impact: str = Field(..., description="影响")
    suggestion: str = Field(..., description="优化建议")

class PerformanceOptimization(BaseModel):
    """性能优化建议"""
    optimization_type: str = Field(..., description="优化类型")
    title: str = Field(..., description="标题")
    description: str = Field(..., description="描述")
    expected_improvement: str = Field(..., description="预期改善")
    implementation_difficulty: str = Field(..., description="实施难度：low/medium/high")
    priority: str = Field(..., description="优先级：low/medium/high")

class PerformanceAnalysis(BaseModel):
    """性能分析结果"""
    task_id: str
    overall_rating: str = Field(..., description="总体评分：excellent/good/fair/poor")
    metrics: PerformanceMetrics
    bottlenecks: List[PerformanceBottleneck] = Field(default_factory=list, description="性能瓶颈")
    optimizations: List[PerformanceOptimization] = Field(default_factory=list, description="优化建议")
    resource_efficiency: Dict[str, float] = Field(default_factory=dict, description="资源效率评分")
    recommendations: List[str] = Field(default_factory=list, description="推荐措施")

class PerformanceReport(BaseModel):
    """性能报告"""
    report_id: str
    task_id: str
    task_type: str
    generated_at: datetime = Field(default_factory=datetime.now)
    format: ReportFormat = Field(default=ReportFormat.PDF, description="报告格式")
    performance_data: TaskPerformanceData
    metrics: PerformanceMetrics
    analysis: PerformanceAnalysis
    historical_comparison: Optional[Dict[str, Any]] = Field(default=None, description="历史对比")
    charts: List[Dict[str, Any]] = Field(default_factory=list, description="图表数据")

class PerformanceReportRequest(BaseModel):
    """性能报告请求"""
    task_id: str
    format: ReportFormat = Field(default=ReportFormat.PDF, description="报告格式")
    include_charts: bool = Field(default=True, description="是否包含图表")
    include_historical_comparison: bool = Field(default=True, description="是否包含历史对比")
    include_analysis: bool = Field(default=True, description="是否包含性能分析")

class PerformanceReportResponse(BaseModel):
    """性能报告响应"""
    report_id: str
    task_id: str
    format: ReportFormat
    status: str
    download_url: Optional[str] = None
    generated_at: datetime

class HistoricalPerformanceStats(BaseModel):
    """历史性能统计"""
    avg_execution_time: float
    min_execution_time: float
    max_execution_time: float
    total_tasks: int
    trend: str = Field(..., description="趋势：improving/stable/degrading")

class PerformanceTrendAnalysis(BaseModel):
    """性能趋势分析"""
    task_id: str
    period_days: int
    current_performance: PerformanceMetrics
    historical_average: HistoricalPerformanceStats
    trend: str
    improvement_rate: Optional[float] = None
    degradation_rate: Optional[float] = None

class PerformanceMetric(BaseModel):
    """单条性能指标"""
    name: str = Field(..., description="指标名称")
    value: float = Field(..., description="指标值")
    ts: int = Field(..., description="时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

class PerformanceMetricsBatch(BaseModel):
    """性能指标批量上报"""
    app: str = Field(..., description="应用名称")
    page: str = Field(..., description="页面路径")
    userAgent: str = Field(..., description="用户代理")
    metrics: List[PerformanceMetric] = Field(..., description="指标列表")
