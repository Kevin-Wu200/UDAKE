"""GPU加速模块的数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class ComputeBackend(str, Enum):
    """计算后端类型。"""

    CPU = "cpu"
    GPU = "gpu"


class TaskStatus(str, Enum):
    """GPU任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GPUDeviceInfo:
    """GPU设备信息。"""

    device_id: int
    name: str
    total_memory_mb: float
    free_memory_mb: float
    compute_capability: Optional[str] = None
    driver_version: Optional[str] = None
    is_available: bool = True
    supports_fp16: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "total_memory_mb": self.total_memory_mb,
            "free_memory_mb": self.free_memory_mb,
            "compute_capability": self.compute_capability,
            "driver_version": self.driver_version,
            "is_available": self.is_available,
            "supports_fp16": self.supports_fp16,
        }


@dataclass
class GPUComputeTask:
    """GPU计算任务定义。"""

    task_id: str
    task_type: str
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    backend: ComputeBackend = ComputeBackend.CPU

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "backend": self.backend.value,
        }


@dataclass
class PerformanceSnapshot:
    """单次计算性能快照。"""

    operation: str
    backend: ComputeBackend
    elapsed_ms: float
    input_size: int
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "backend": self.backend.value,
            "elapsed_ms": round(self.elapsed_ms, 4),
            "input_size": self.input_size,
            "timestamp": self.timestamp.isoformat(),
        }
