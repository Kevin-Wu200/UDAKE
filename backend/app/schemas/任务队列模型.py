"""
任务队列模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class QueueTaskStatus(str, Enum):
    """队列任务状态"""
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"

class QueueTaskPriority(str, Enum):
    """队列任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class QueueTaskInfo(BaseModel):
    """队列任务信息"""
    task_id: str
    task_type: str = Field(..., description="任务类型")
    priority: QueueTaskPriority = Field(default=QueueTaskPriority.MEDIUM, description="任务优先级")
    status: QueueTaskStatus = Field(default=QueueTaskStatus.WAITING, description="任务状态")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="任务进度")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    estimated_duration: Optional[float] = Field(default=None, description="预计耗时（秒）")
    actual_duration: Optional[float] = Field(default=None, description="实际耗时（秒）")
    error: Optional[str] = Field(default=None, description="错误信息")
    retry_count: int = Field(default=0, description="重试次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")

class QueueStatistics(BaseModel):
    """队列统计信息"""
    total_tasks: int = Field(default=0, description="总任务数")
    waiting_tasks: int = Field(default=0, description="等待中任务数")
    running_tasks: int = Field(default=0, description="运行中任务数")
    completed_tasks: int = Field(default=0, description="已完成任务数")
    failed_tasks: int = Field(default=0, description="失败任务数")
    paused_tasks: int = Field(default=0, description="暂停任务数")
    cancelled_tasks: int = Field(default=0, description="取消任务数")
    avg_completion_time: Optional[float] = Field(default=None, description="平均完成时间（秒）")
    success_rate: float = Field(default=0.0, description="成功率")
    throughput: float = Field(default=0.0, description="吞吐量（任务/小时）")

class QueueVisualization(BaseModel):
    """队列可视化数据"""
    statistics: QueueStatistics
    tasks_by_status: Dict[str, int] = Field(default_factory=dict, description="按状态分组的任务数")
    tasks_by_priority: Dict[str, int] = Field(default_factory=dict, description="按优先级分组的任务数")
    timeline: List[Dict[str, Any]] = Field(default_factory=list, description="任务时间线")
    queue_flow: List[Dict[str, Any]] = Field(default_factory=list, description="队列流程图")

class TaskControlRequest(BaseModel):
    """任务控制请求"""
    task_id: str
    action: str = Field(..., description="操作类型：pause/resume/cancel/retry")

class TaskControlResponse(BaseModel):
    """任务控制响应"""
    task_id: str
    action: str
    status: str
    message: str

class TaskPriorityUpdateRequest(BaseModel):
    """任务优先级更新请求"""
    task_id: str
    priority: QueueTaskPriority

class BatchTaskControlRequest(BaseModel):
    """批量任务控制请求"""
    task_ids: List[str] = Field(..., description="任务ID列表")
    action: str = Field(..., description="操作类型：pause/resume/cancel/retry")

class BatchTaskControlResponse(BaseModel):
    """批量任务控制响应"""
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    results: List[TaskControlResponse]

class QueueConfig(BaseModel):
    """队列配置"""
    max_concurrent_tasks: int = Field(default=5, description="最大并发任务数", ge=1, le=20)
    queue_size_limit: int = Field(default=100, description="队列大小限制", ge=1, le=1000)
    enable_auto_retry: bool = Field(default=True, description="是否启用自动重试")
    max_retry_attempts: int = Field(default=3, description="最大重试次数", ge=0, le=10)
    retry_delay: int = Field(default=60, description="重试延迟（秒）", ge=0, le=3600)
    priority_scheduling: bool = Field(default=True, description="是否启用优先级调度")
    fair_scheduling: bool = Field(default=True, description="是否启用公平调度")
    enable_task_timeout: bool = Field(default=True, description="是否启用任务超时")
    task_timeout: int = Field(default=3600, description="任务超时时间（秒）", ge=60, le=86400)