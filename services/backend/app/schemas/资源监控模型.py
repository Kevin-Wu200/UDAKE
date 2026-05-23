"""
资源监控模型
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    """资源类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"

class ResourceUsage(BaseModel):
    """资源使用情况"""
    resource_type: ResourceType
    usage_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="使用率百分比")
    used_value: float = Field(default=0.0, description="已使用量")
    total_value: float = Field(default=0.0, description="总量")
    unit: str = Field(default="", description="单位")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")

class SystemResources(BaseModel):
    """系统资源使用情况"""
    cpu: ResourceUsage
    memory: ResourceUsage
    disk: ResourceUsage
    network: Optional[Dict[str, float]] = Field(default=None, description="网络使用情况")
    timestamp: datetime = Field(default_factory=datetime.now)

class TaskResourceUsage(BaseModel):
    """任务资源使用情况"""
    task_id: str
    cpu_usage: float = Field(default=0.0, ge=0.0, le=100.0, description="CPU使用率")
    memory_usage: float = Field(default=0.0, description="内存使用量（MB）")
    disk_usage: float = Field(default=0.0, description="磁盘使用量（MB）")
    network_usage: Optional[Dict[str, float]] = Field(default=None, description="网络使用量")
    timestamp: datetime = Field(default_factory=datetime.now)

class ResourceWarning(BaseModel):
    """资源警告"""
    warning_id: str
    resource_type: ResourceType
    warning_level: str = Field(..., description="警告级别：warning/critical")
    message: str
    threshold: float = Field(..., description="阈值")
    current_value: float = Field(..., description="当前值")
    task_id: Optional[str] = Field(default=None, description="相关任务ID")
    timestamp: datetime = Field(default_factory=datetime.now)

class ResourceOptimizationSuggestion(BaseModel):
    """资源优化建议"""
    suggestion_id: str
    resource_type: ResourceType
    suggestion_type: str = Field(..., description="建议类型：reduce_concurrent/batch_processing/cleanup_temp")
    title: str
    description: str
    priority: str = Field(..., description="优先级：high/medium/low")
    expected_improvement: Optional[str] = Field(default=None, description="预期改善")
    action_steps: List[str] = Field(..., description="行动步骤")
    timestamp: datetime = Field(default_factory=datetime.now)

class ResourceMonitoringConfig(BaseModel):
    """资源监控配置"""
    cpu_warning_threshold: float = Field(default=80.0, ge=0.0, le=100.0, description="CPU警告阈值")
    cpu_critical_threshold: float = Field(default=90.0, ge=0.0, le=100.0, description="CPU严重阈值")
    memory_warning_threshold: float = Field(default=80.0, ge=0.0, le=100.0, description="内存警告阈值")
    memory_critical_threshold: float = Field(default=90.0, ge=0.0, le=100.0, description="内存严重阈值")
    disk_warning_threshold: float = Field(default=80.0, ge=0.0, le=100.0, description="磁盘警告阈值")
    disk_critical_threshold: float = Field(default=90.0, ge=0.0, le=100.0, description="磁盘严重阈值")
    monitoring_interval: int = Field(default=5, ge=1, description="监控间隔（秒）")
    enable_optimization_suggestions: bool = Field(default=True, description="是否启用优化建议")

class ResourceStatistics(BaseModel):
    """资源统计信息"""
    resource_type: ResourceType
    avg_usage: float = Field(default=0.0, description="平均使用率")
    max_usage: float = Field(default=0.0, description="最大使用率")
    min_usage: float = Field(default=0.0, description="最小使用率")
    peak_usage_time: Optional[datetime] = Field(default=None, description="峰值使用时间")
    total_samples: int = Field(default=0, description="总采样数")
    period_start: datetime
    period_end: datetime
