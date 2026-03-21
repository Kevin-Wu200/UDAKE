"""
批量处理模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from .插值参数模型 import KrigingParameters, KrigingMethod, VariogramModel

class BatchTaskExecutionMode(str, Enum):
    """批量任务执行模式"""
    SERIAL = "serial"
    PARALLEL = "parallel"

class BatchTaskPriority(str, Enum):
    """批量任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class BatchTaskStatus(str, Enum):
    """批量任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BatchKrigingRequest(BaseModel):
    """批量克里金请求"""
    data_ids: List[str] = Field(..., description="数据ID列表")
    parameters: Optional[KrigingParameters] = Field(default=None, description="统一参数（如果提供，所有任务使用相同参数）")
    individual_parameters: Optional[Dict[str, KrigingParameters]] = Field(default=None, description="单独参数字典（键为数据ID）")
    execution_mode: BatchTaskExecutionMode = Field(default=BatchTaskExecutionMode.PARALLEL, description="执行模式")
    priority: BatchTaskPriority = Field(default=BatchTaskPriority.MEDIUM, description="任务优先级")
    max_concurrent: Optional[int] = Field(default=4, description="最大并发任务数（仅并行模式有效）")
    description: Optional[str] = Field(default=None, description="任务描述")

class BatchTaskStartResponse(BaseModel):
    """批量任务启动响应"""
    batch_id: str
    status: str
    message: str
    total_tasks: int
    estimated_duration: Optional[float] = Field(default=None, description="预计耗时（秒）")

class BatchTaskSummary(BaseModel):
    """批量任务摘要"""
    batch_id: str
    total_tasks: int
    completed_tasks: int
    running_tasks: int
    failed_tasks: int
    pending_tasks: int
    overall_progress: float = Field(default=0.0, ge=0.0, le=100.0)
    status: BatchTaskStatus
    created_at: datetime
    updated_at: datetime
    message: Optional[str] = None
    estimated_remaining_time: Optional[float] = Field(default=None, description="预计剩余时间（秒）")

class BatchTaskDetail(BaseModel):
    """批量任务详情"""
    task_id: str
    data_id: str
    status: str
    progress: float
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    parameters: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None

class BatchTaskFullResponse(BaseModel):
    """批量任务完整响应"""
    summary: BatchTaskSummary
    tasks: List[BatchTaskDetail]

class BatchTaskControlRequest(BaseModel):
    """批量任务控制请求"""
    action: str = Field(..., description="操作类型：pause/resume/cancel")

class BatchTaskControlResponse(BaseModel):
    """批量任务控制响应"""
    batch_id: str
    action: str
    status: str
    message: str

class BatchTaskResultsSummary(BaseModel):
    """批量任务结果汇总"""
    batch_id: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    success_rate: float
    results: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    generated_at: datetime

class ParameterTemplate(BaseModel):
    """参数模板"""
    template_id: str
    name: str
    description: Optional[str] = Field(default=None, description="模板描述")
    industry: Optional[str] = Field(default=None, description="行业类型")
    parameters: KrigingParameters
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)

class ParameterTemplateListResponse(BaseModel):
    """参数模板列表响应"""
    templates: List[ParameterTemplate]
    total: int

class ParameterTemplateSaveRequest(BaseModel):
    """参数模板保存请求"""
    name: str
    description: Optional[str] = Field(default=None)
    industry: Optional[str] = Field(default=None)
    parameters: KrigingParameters

class ParameterBatchApplyRequest(BaseModel):
    """参数批量应用请求"""
    template_id: Optional[str] = Field(default=None, description="模板ID")
    parameters: Optional[KrigingParameters] = Field(default=None, description="统一参数")
    individual_parameters: Optional[Dict[str, KrigingParameters]] = Field(default=None, description="单独参数字典")
    data_ids: List[str] = Field(..., description="数据ID列表")
    auto_adjust: bool = Field(default=True, description="是否根据数据自动调整参数")

class ParameterValidationResult(BaseModel):
    """参数验证结果"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)

class ResultComparisonMetrics(BaseModel):
    """结果对比指标"""
    task_id: str
    data_id: str
    rmse: Optional[float] = Field(default=None)
    mae: Optional[float] = Field(default=None)
    r2: Optional[float] = Field(default=None)
    mse: Optional[float] = Field(default=None)
    execution_time: Optional[float] = Field(default=None)
    point_count: Optional[int] = Field(default=None)

class ResultComparisonResponse(BaseModel):
    """结果对比响应"""
    batch_id: str
    metrics: List[ResultComparisonMetrics]
    statistics: Dict[str, Any]
    best_result: Optional[Dict[str, Any]] = Field(default=None)
    worst_result: Optional[Dict[str, Any]] = Field(default=None)
    generated_at: datetime

class BatchReportRequest(BaseModel):
    """批量报告请求"""
    batch_id: str
    report_title: Optional[str] = Field(default=None, description="报告标题")
    report_description: Optional[str] = Field(default=None, description="报告描述")
    include_sections: Optional[List[str]] = Field(default=None, description="包含的章节")
    chart_types: Optional[Dict[str, str]] = Field(default=None, description="图表类型配置")
    format: str = Field(default="pdf", description="报告格式：pdf/html/word/excel")

class BatchReportResponse(BaseModel):
    """批量报告响应"""
    report_id: str
    batch_id: str
    format: str
    status: str
    download_url: Optional[str] = Field(default=None)
    generated_at: datetime