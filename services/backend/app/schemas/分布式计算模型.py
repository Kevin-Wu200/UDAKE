"""分布式计算相关的数据模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DistributedFramework(str, Enum):
    """可选分布式框架。"""

    RAY = "ray"
    DASK = "dask"
    LOCAL = "local"


class DistributedTaskStatus(str, Enum):
    """任务状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(str, Enum):
    """节点状态。"""

    ONLINE = "online"
    OFFLINE = "offline"


class ResourceRequirement(BaseModel):
    """任务资源需求。"""

    cpu_cores: int = Field(default=1, ge=1, le=64)
    memory_mb: int = Field(default=256, ge=64, le=1048576)
    data_locality: Optional[str] = Field(default=None, description="数据本地化节点ID")


class DistributedTaskSubmitRequest(BaseModel):
    """提交分布式任务请求。"""

    task_type: str = Field(..., description="任务类型")
    payload: Dict[str, Any] = Field(default_factory=dict, description="任务载荷")
    priority: int = Field(default=5, ge=0, le=9, description="优先级，数值越小优先级越高")
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=2, ge=0, le=600)
    resource_requirement: ResourceRequirement = Field(default_factory=ResourceRequirement)


class DistributedTaskInfo(BaseModel):
    """分布式任务信息。"""

    task_id: str
    task_type: str
    framework: DistributedFramework
    status: DistributedTaskStatus
    priority: int
    node_id: Optional[str] = None
    attempt: int = 0
    max_retries: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    resource_requirement: ResourceRequirement


class NodeRegisterRequest(BaseModel):
    """注册节点请求。"""

    node_id: str = Field(..., min_length=1, max_length=128)
    cpu_capacity: int = Field(default=4, ge=1, le=256)
    memory_capacity_mb: int = Field(default=4096, ge=256, le=1048576)
    labels: Dict[str, str] = Field(default_factory=dict)


class NodeHeartbeatRequest(BaseModel):
    """节点心跳请求。"""

    node_id: str = Field(..., min_length=1, max_length=128)
    cpu_used: float = Field(default=0.0, ge=0.0, le=1.0)
    memory_used: float = Field(default=0.0, ge=0.0, le=1.0)


class NodeInfoResponse(BaseModel):
    """节点信息响应。"""

    node_id: str
    status: NodeStatus
    cpu_capacity: int
    memory_capacity_mb: int
    cpu_used: float
    memory_used: float
    active_tasks: int
    labels: Dict[str, str]
    last_heartbeat: datetime


class DistributedTaskSubmitResponse(BaseModel):
    """提交任务响应。"""

    task_id: str
    message: str


class TaskListResponse(BaseModel):
    """任务列表响应。"""

    tasks: List[DistributedTaskInfo]


class ClusterOverviewResponse(BaseModel):
    """集群概览。"""

    preferred_framework: DistributedFramework
    active_framework: DistributedFramework
    total_nodes: int
    online_nodes: int
    offline_nodes: int
    queue_size: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int


class MetricsResponse(BaseModel):
    """性能监控指标。"""

    task_success_rate: float
    avg_task_duration_seconds: float
    queue_depth: int
    resource_utilization: float
    cache_hit_rate: float
    estimated_acceleration_ratio: float
    autoscaling_recommended: bool


class CheckpointResponse(BaseModel):
    """检查点响应。"""

    task_id: str
    checkpoint_id: str
    created_at: datetime


class RecoveryResponse(BaseModel):
    """恢复响应。"""

    task_id: str
    recovered: bool
    message: str


class ScaleSuggestionResponse(BaseModel):
    """扩缩容建议。"""

    recommendation: str
    suggested_node_delta: int
    reason: str
