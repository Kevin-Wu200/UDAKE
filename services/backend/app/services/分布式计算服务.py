"""分布式计算服务。

目标：
1. 提供 Ray/Dask/本地回退的统一执行入口。
2. 提供任务调度、负载均衡、心跳监控、故障恢复、自动重试。
3. 提供检查点、备份恢复、监控指标与扩缩容建议。
"""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import math
import threading
import time
import uuid
import zlib
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..schemas.分布式计算模型 import (
    CheckpointResponse,
    ClusterOverviewResponse,
    DistributedFramework,
    DistributedTaskInfo,
    DistributedTaskStatus,
    DistributedTaskSubmitRequest,
    MetricsResponse,
    NodeHeartbeatRequest,
    NodeInfoResponse,
    NodeRegisterRequest,
    NodeStatus,
    RecoveryResponse,
    ResourceRequirement,
    ScaleSuggestionResponse,
)


@dataclass
class _NodeState:
    node_id: str
    cpu_capacity: int
    memory_capacity_mb: int
    labels: Dict[str, str] = field(default_factory=dict)
    status: NodeStatus = NodeStatus.ONLINE
    cpu_used: float = 0.0
    memory_used: float = 0.0
    reserved_cpu_cores: int = 0
    reserved_memory_mb: int = 0
    active_tasks: set[str] = field(default_factory=set)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)


@dataclass
class _TaskState:
    task_id: str
    task_type: str
    framework: DistributedFramework
    status: DistributedTaskStatus
    priority: int
    payload: Any
    payload_compressed: bool
    payload_size_bytes: int
    payload_chunks: int
    resource_requirement: ResourceRequirement
    max_retries: int
    retry_delay_seconds: int
    attempt: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    next_run_at: datetime = field(default_factory=datetime.utcnow)
    node_id: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    cache_key: str = ""


class DistributedComputeService:
    """分布式计算服务实现。"""

    def __init__(
        self,
        preferred_framework: DistributedFramework = DistributedFramework.RAY,
        heartbeat_timeout_seconds: int = 30,
        max_workers: int = 8,
    ) -> None:
        self.preferred_framework = preferred_framework
        self.active_framework = self._select_framework(preferred_framework)
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds

        self._lock = threading.RLock()
        self._tasks: Dict[str, _TaskState] = {}
        self._nodes: Dict[str, _NodeState] = {}

        self._checkpoint_root = Path(__file__).resolve().parents[1] / "结果文件" / "distributed_checkpoints"
        self._backup_file = Path(__file__).resolve().parents[1] / "结果文件" / "distributed_cluster_backup.json"
        self._checkpoint_root.mkdir(parents=True, exist_ok=True)
        self._backup_file.parent.mkdir(parents=True, exist_ok=True)

        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="distributed-worker")
        self._scheduler_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running = False

        self._event_log: deque[Dict[str, Any]] = deque(maxlen=400)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._duration_samples: List[float] = []
        self._baseline_samples: List[float] = []

        self._register_builtin_local_node()

    def _select_framework(self, preferred: DistributedFramework) -> DistributedFramework:
        """选择实际可用的执行框架。"""
        preferred_map = {
            DistributedFramework.RAY: "ray",
            DistributedFramework.DASK: "dask",
        }
        preferred_pkg = preferred_map.get(preferred)
        if preferred_pkg and importlib.util.find_spec(preferred_pkg):
            return preferred

        if importlib.util.find_spec("ray"):
            return DistributedFramework.RAY
        if importlib.util.find_spec("dask"):
            return DistributedFramework.DASK
        return DistributedFramework.LOCAL

    def _register_builtin_local_node(self) -> None:
        with self._lock:
            if "local-node-1" not in self._nodes:
                self._nodes["local-node-1"] = _NodeState(
                    node_id="local-node-1",
                    cpu_capacity=8,
                    memory_capacity_mb=16384,
                    labels={"zone": "local", "role": "default"},
                )

    def start(self) -> None:
        """启动调度与监控线程。"""
        with self._lock:
            if self._running:
                return
            self._running = True

        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="distributed-scheduler")
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="distributed-heartbeat")
        self._scheduler_thread.start()
        self._heartbeat_thread.start()
        self._record_event("service_started", {"framework": self.active_framework.value})

    def stop(self) -> None:
        """停止后台线程。"""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2)
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)
        self._record_event("service_stopped", {})

    def submit_task(self, request: DistributedTaskSubmitRequest) -> str:
        """提交任务到分布式调度系统。"""
        self.start()
        task_id = uuid.uuid4().hex
        prepared = self._prepare_payload(request.payload)
        cache_key = self._build_cache_key(request.task_type, request.payload)

        task = _TaskState(
            task_id=task_id,
            task_type=request.task_type,
            framework=self.active_framework,
            status=DistributedTaskStatus.QUEUED,
            priority=request.priority,
            payload=prepared["payload"],
            payload_compressed=prepared["compressed"],
            payload_size_bytes=prepared["payload_size"],
            payload_chunks=prepared["chunks"],
            resource_requirement=request.resource_requirement.model_copy(deep=True),
            max_retries=request.max_retries,
            retry_delay_seconds=request.retry_delay_seconds,
            cache_key=cache_key,
        )

        with self._lock:
            self._tasks[task_id] = task
            self._cache_misses += 1

        self._record_event(
            "task_submitted",
            {
                "task_id": task_id,
                "task_type": request.task_type,
                "priority": request.priority,
                "compressed": prepared["compressed"],
                "chunks": prepared["chunks"],
            },
        )
        return task_id

    def get_task(self, task_id: str) -> Optional[DistributedTaskInfo]:
        with self._lock:
            task = self._tasks.get(task_id)
            return self._to_task_info(task) if task else None

    def list_tasks(self, status: Optional[DistributedTaskStatus] = None, limit: int = 200) -> List[DistributedTaskInfo]:
        with self._lock:
            values = list(self._tasks.values())
            if status:
                values = [task for task in values if task.status == status]
            values.sort(key=lambda item: item.created_at, reverse=True)
            return [self._to_task_info(task) for task in values[:limit]]

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in {DistributedTaskStatus.COMPLETED, DistributedTaskStatus.FAILED, DistributedTaskStatus.CANCELLED}:
                return False
            task.status = DistributedTaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            if task.node_id and task.node_id in self._nodes:
                self._release_node_resources(task, self._nodes[task.node_id])
            task.node_id = None

        self._record_event("task_cancelled", {"task_id": task_id})
        return True

    def register_node(self, request: NodeRegisterRequest) -> NodeInfoResponse:
        self.start()
        with self._lock:
            state = self._nodes.get(request.node_id)
            if state is None:
                state = _NodeState(
                    node_id=request.node_id,
                    cpu_capacity=request.cpu_capacity,
                    memory_capacity_mb=request.memory_capacity_mb,
                    labels=dict(request.labels),
                )
                self._nodes[request.node_id] = state
            else:
                state.cpu_capacity = request.cpu_capacity
                state.memory_capacity_mb = request.memory_capacity_mb
                state.labels = dict(request.labels)
                state.status = NodeStatus.ONLINE
                state.last_heartbeat = datetime.utcnow()

        self._record_event("node_registered", {"node_id": request.node_id})
        return self._to_node_info(state)

    def heartbeat(self, request: NodeHeartbeatRequest) -> NodeInfoResponse:
        with self._lock:
            if request.node_id not in self._nodes:
                self._nodes[request.node_id] = _NodeState(
                    node_id=request.node_id,
                    cpu_capacity=4,
                    memory_capacity_mb=4096,
                    labels={"auto_discovered": "true"},
                )

            node = self._nodes[request.node_id]
            node.status = NodeStatus.ONLINE
            node.last_heartbeat = datetime.utcnow()
            node.cpu_used = max(0.0, min(1.0, request.cpu_used))
            node.memory_used = max(0.0, min(1.0, request.memory_used))

        return self._to_node_info(node)

    def list_nodes(self) -> List[NodeInfoResponse]:
        with self._lock:
            nodes = list(self._nodes.values())
            nodes.sort(key=lambda item: item.node_id)
            return [self._to_node_info(node) for node in nodes]

    def get_cluster_overview(self) -> ClusterOverviewResponse:
        with self._lock:
            tasks = list(self._tasks.values())
            total_nodes = len(self._nodes)
            online_nodes = len([node for node in self._nodes.values() if node.status == NodeStatus.ONLINE])
            offline_nodes = total_nodes - online_nodes

            return ClusterOverviewResponse(
                preferred_framework=self.preferred_framework,
                active_framework=self.active_framework,
                total_nodes=total_nodes,
                online_nodes=online_nodes,
                offline_nodes=offline_nodes,
                queue_size=len([task for task in tasks if task.status == DistributedTaskStatus.QUEUED]),
                running_tasks=len([task for task in tasks if task.status == DistributedTaskStatus.RUNNING]),
                completed_tasks=len([task for task in tasks if task.status == DistributedTaskStatus.COMPLETED]),
                failed_tasks=len([task for task in tasks if task.status == DistributedTaskStatus.FAILED]),
            )

    def get_metrics(self) -> MetricsResponse:
        with self._lock:
            tasks = list(self._tasks.values())
            completed = [task for task in tasks if task.status == DistributedTaskStatus.COMPLETED]
            finished = [task for task in tasks if task.status in (DistributedTaskStatus.COMPLETED, DistributedTaskStatus.FAILED)]
            success_rate = (len(completed) / len(finished)) if finished else 1.0

            avg_duration = float(sum(self._duration_samples) / len(self._duration_samples)) if self._duration_samples else 0.0
            queue_depth = len([task for task in tasks if task.status == DistributedTaskStatus.QUEUED])

            online_nodes = [node for node in self._nodes.values() if node.status == NodeStatus.ONLINE]
            if online_nodes:
                utilization = sum(self._node_load(node) for node in online_nodes) / len(online_nodes)
            else:
                utilization = 0.0

            total_cache_queries = self._cache_hits + self._cache_misses
            cache_hit_rate = (self._cache_hits / total_cache_queries) if total_cache_queries else 0.0

            if self._duration_samples and self._baseline_samples and len(self._duration_samples) == len(self._baseline_samples):
                ratios = [
                    min(2.0, baseline / max(duration, 1e-6))
                    for baseline, duration in zip(self._baseline_samples, self._duration_samples)
                ]
                acceleration_ratio = float(sum(ratios) / len(ratios))
            else:
                acceleration_ratio = 1.0

        scaling = self.get_scale_suggestion()
        return MetricsResponse(
            task_success_rate=round(success_rate, 4),
            avg_task_duration_seconds=round(avg_duration, 4),
            queue_depth=queue_depth,
            resource_utilization=round(utilization, 4),
            cache_hit_rate=round(cache_hit_rate, 4),
            estimated_acceleration_ratio=round(acceleration_ratio, 4),
            autoscaling_recommended=scaling.suggested_node_delta != 0,
        )

    def get_scale_suggestion(self) -> ScaleSuggestionResponse:
        with self._lock:
            queue_depth = len([task for task in self._tasks.values() if task.status == DistributedTaskStatus.QUEUED])
            online_nodes = [node for node in self._nodes.values() if node.status == NodeStatus.ONLINE]
            node_count = len(online_nodes)
            utilization = sum(self._node_load(node) for node in online_nodes) / node_count if node_count else 1.0

        if utilization > 0.8 and queue_depth > max(1, node_count):
            delta = max(1, math.ceil(queue_depth / max(node_count, 1)) - 1)
            return ScaleSuggestionResponse(
                recommendation="scale_out",
                suggested_node_delta=delta,
                reason="队列积压且资源利用率高，建议扩容节点",
            )

        if utilization < 0.2 and queue_depth == 0 and node_count > 1:
            return ScaleSuggestionResponse(
                recommendation="scale_in",
                suggested_node_delta=-1,
                reason="空闲资源较多且无队列积压，建议缩容",
            )

        return ScaleSuggestionResponse(
            recommendation="stable",
            suggested_node_delta=0,
            reason="当前负载平稳，维持现有规模",
        )

    def create_checkpoint(self, task_id: str) -> CheckpointResponse:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise ValueError("任务不存在")
            snapshot = self._serialize_task(task)

        checkpoint_id = f"{task_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        task_dir = self._checkpoint_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = task_dir / f"{checkpoint_id}.json"
        checkpoint_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

        self._record_event("checkpoint_created", {"task_id": task_id, "checkpoint_id": checkpoint_id})
        return CheckpointResponse(task_id=task_id, checkpoint_id=checkpoint_id, created_at=datetime.utcnow())

    def recover_task(self, task_id: str, checkpoint_id: Optional[str] = None) -> RecoveryResponse:
        task_dir = self._checkpoint_root / task_id
        if not task_dir.exists():
            return RecoveryResponse(task_id=task_id, recovered=False, message="未找到检查点")

        checkpoints = sorted(task_dir.glob("*.json"))
        if not checkpoints:
            return RecoveryResponse(task_id=task_id, recovered=False, message="未找到检查点")

        selected: Optional[Path] = None
        if checkpoint_id:
            expected = task_dir / f"{checkpoint_id}.json"
            if expected.exists():
                selected = expected
            else:
                return RecoveryResponse(task_id=task_id, recovered=False, message="指定检查点不存在")
        else:
            selected = checkpoints[-1]

        payload = json.loads(selected.read_text(encoding="utf-8"))

        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return RecoveryResponse(task_id=task_id, recovered=False, message="任务不存在")

            if task.node_id and task.node_id in self._nodes:
                self._release_node_resources(task, self._nodes[task.node_id])

            task.status = DistributedTaskStatus.QUEUED
            task.error = None
            task.result = None
            task.node_id = None
            task.started_at = None
            task.completed_at = None
            task.next_run_at = datetime.utcnow()

            # 仅恢复与执行相关字段，避免破坏任务标识。
            task.payload = payload.get("payload", task.payload)
            task.payload_compressed = bool(payload.get("payload_compressed", task.payload_compressed))
            task.payload_size_bytes = int(payload.get("payload_size_bytes", task.payload_size_bytes))
            task.payload_chunks = int(payload.get("payload_chunks", task.payload_chunks))

        self._record_event("task_recovered", {"task_id": task_id, "checkpoint": selected.name})
        return RecoveryResponse(task_id=task_id, recovered=True, message="任务已恢复并重新排队")

    def backup_cluster_state(self) -> str:
        with self._lock:
            state = {
                "created_at": datetime.utcnow().isoformat(),
                "framework": self.active_framework.value,
                "tasks": [self._serialize_task(task) for task in self._tasks.values()],
                "nodes": [self._serialize_node(node) for node in self._nodes.values()],
            }
        self._backup_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        self._record_event("cluster_backup", {"path": str(self._backup_file)})
        return str(self._backup_file)

    def restore_cluster_state(self) -> bool:
        if not self._backup_file.exists():
            return False

        content = json.loads(self._backup_file.read_text(encoding="utf-8"))
        with self._lock:
            self._tasks.clear()
            self._nodes.clear()
            for node_payload in content.get("nodes", []):
                node = _NodeState(
                    node_id=node_payload["node_id"],
                    cpu_capacity=node_payload["cpu_capacity"],
                    memory_capacity_mb=node_payload["memory_capacity_mb"],
                    labels=node_payload.get("labels", {}),
                    status=NodeStatus(node_payload.get("status", NodeStatus.ONLINE.value)),
                    cpu_used=float(node_payload.get("cpu_used", 0.0)),
                    memory_used=float(node_payload.get("memory_used", 0.0)),
                    reserved_cpu_cores=int(node_payload.get("reserved_cpu_cores", 0)),
                    reserved_memory_mb=int(node_payload.get("reserved_memory_mb", 0)),
                    active_tasks=set(node_payload.get("active_tasks", [])),
                    last_heartbeat=datetime.fromisoformat(node_payload["last_heartbeat"]),
                )
                self._nodes[node.node_id] = node

            for task_payload in content.get("tasks", []):
                task = _TaskState(
                    task_id=task_payload["task_id"],
                    task_type=task_payload["task_type"],
                    framework=DistributedFramework(task_payload["framework"]),
                    status=DistributedTaskStatus(task_payload["status"]),
                    priority=int(task_payload["priority"]),
                    payload=task_payload.get("payload", {}),
                    payload_compressed=bool(task_payload.get("payload_compressed", False)),
                    payload_size_bytes=int(task_payload.get("payload_size_bytes", 0)),
                    payload_chunks=int(task_payload.get("payload_chunks", 1)),
                    resource_requirement=ResourceRequirement(**task_payload.get("resource_requirement", {})),
                    max_retries=int(task_payload.get("max_retries", 0)),
                    retry_delay_seconds=int(task_payload.get("retry_delay_seconds", 0)),
                    attempt=int(task_payload.get("attempt", 0)),
                    created_at=datetime.fromisoformat(task_payload["created_at"]),
                    started_at=datetime.fromisoformat(task_payload["started_at"]) if task_payload.get("started_at") else None,
                    completed_at=datetime.fromisoformat(task_payload["completed_at"]) if task_payload.get("completed_at") else None,
                    next_run_at=datetime.fromisoformat(task_payload["next_run_at"]),
                    node_id=task_payload.get("node_id"),
                    error=task_payload.get("error"),
                    result=task_payload.get("result"),
                    cache_key=task_payload.get("cache_key", ""),
                )
                self._tasks[task.task_id] = task

            if not self._nodes:
                self._register_builtin_local_node()

        self._record_event("cluster_restored", {"path": str(self._backup_file)})
        return True

    def get_event_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            values = list(self._event_log)[-max(1, limit):]
        return copy.deepcopy(values)

    def _scheduler_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                task = self._pick_next_task_locked()

            if task is None:
                time.sleep(0.1)
                continue

            if self._try_finish_from_cache(task):
                continue

            node = self._select_node_for_task(task)
            if node is None:
                time.sleep(0.05)
                continue

            with self._lock:
                fresh_task = self._tasks.get(task.task_id)
                fresh_node = self._nodes.get(node.node_id)
                if not fresh_task or not fresh_node:
                    continue
                if fresh_task.status != DistributedTaskStatus.QUEUED:
                    continue

                fresh_task.status = DistributedTaskStatus.RUNNING
                fresh_task.started_at = datetime.utcnow()
                fresh_task.node_id = fresh_node.node_id
                fresh_task.attempt += 1
                fresh_task.error = None

                self._reserve_node_resources(fresh_task, fresh_node)
                self._record_event(
                    "task_dispatched",
                    {
                        "task_id": fresh_task.task_id,
                        "node_id": fresh_node.node_id,
                        "attempt": fresh_task.attempt,
                    },
                )

            self._executor.submit(self._execute_task, task.task_id)

    def _heartbeat_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                now = datetime.utcnow()
                timeout = timedelta(seconds=self.heartbeat_timeout_seconds)

                for node in self._nodes.values():
                    if node.node_id.startswith("local-node-"):
                        node.status = NodeStatus.ONLINE
                        node.last_heartbeat = now
                        continue
                    if now - node.last_heartbeat > timeout:
                        node.status = NodeStatus.OFFLINE

                # 节点离线时自动把任务回收并重新排队。
                for task in self._tasks.values():
                    if task.status != DistributedTaskStatus.RUNNING or not task.node_id:
                        continue
                    node = self._nodes.get(task.node_id)
                    if not node or node.status == NodeStatus.ONLINE:
                        continue

                    self._release_node_resources(task, node)
                    task.status = DistributedTaskStatus.QUEUED
                    task.error = "节点离线，任务已自动重新调度"
                    task.node_id = None
                    task.started_at = None
                    task.next_run_at = datetime.utcnow() + timedelta(seconds=1)
                    self._record_event("task_rescheduled", {"task_id": task.task_id})

            time.sleep(1)

    def _pick_next_task_locked(self) -> Optional[_TaskState]:
        now = datetime.utcnow()
        queued = [
            task
            for task in self._tasks.values()
            if task.status == DistributedTaskStatus.QUEUED and task.next_run_at <= now
        ]
        if not queued:
            return None

        queued.sort(key=lambda item: (item.priority, item.created_at))
        return queued[0]

    def _select_node_for_task(self, task: _TaskState) -> Optional[_NodeState]:
        with self._lock:
            online_nodes = [node for node in self._nodes.values() if node.status == NodeStatus.ONLINE]
            if not online_nodes:
                return None

            req = task.resource_requirement
            candidates: List[_NodeState] = []
            for node in online_nodes:
                cpu_available = node.cpu_capacity - node.reserved_cpu_cores
                memory_available = node.memory_capacity_mb - node.reserved_memory_mb
                if cpu_available >= req.cpu_cores and memory_available >= req.memory_mb:
                    candidates.append(node)

            if not candidates:
                return None

            if req.data_locality:
                localized = [node for node in candidates if node.node_id == req.data_locality]
                if localized:
                    return localized[0]

            candidates.sort(key=self._node_load)
            return candidates[0]

    def _node_load(self, node: _NodeState) -> float:
        cpu_load = node.reserved_cpu_cores / max(node.cpu_capacity, 1)
        mem_load = node.reserved_memory_mb / max(node.memory_capacity_mb, 1)
        return (cpu_load + mem_load) / 2.0

    def _reserve_node_resources(self, task: _TaskState, node: _NodeState) -> None:
        node.active_tasks.add(task.task_id)
        node.reserved_cpu_cores += task.resource_requirement.cpu_cores
        node.reserved_memory_mb += task.resource_requirement.memory_mb

    def _release_node_resources(self, task: _TaskState, node: _NodeState) -> None:
        node.active_tasks.discard(task.task_id)
        node.reserved_cpu_cores = max(0, node.reserved_cpu_cores - task.resource_requirement.cpu_cores)
        node.reserved_memory_mb = max(0, node.reserved_memory_mb - task.resource_requirement.memory_mb)

    def _try_finish_from_cache(self, task: _TaskState) -> bool:
        with self._lock:
            cached = self._cache.get(task.cache_key)
            if cached is None:
                return False

            current = self._tasks.get(task.task_id)
            if current is None or current.status != DistributedTaskStatus.QUEUED:
                return True

            current.status = DistributedTaskStatus.COMPLETED
            current.completed_at = datetime.utcnow()
            current.result = {
                **copy.deepcopy(cached),
                "from_cache": True,
            }
            self._cache_hits += 1

        self._record_event("task_cache_hit", {"task_id": task.task_id})
        return True

    def _execute_task(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != DistributedTaskStatus.RUNNING:
                return
            node = self._nodes.get(task.node_id) if task.node_id else None
            start_time = task.started_at or datetime.utcnow()
            current_attempt = task.attempt

        try:
            self.create_checkpoint(task_id)
            payload = self._restore_payload(task.payload, task.payload_compressed)
            result = self._run_task_logic(task.task_type, payload, current_attempt)

            duration = (datetime.utcnow() - start_time).total_seconds()
            baseline = float(result.get("estimated_sequential_seconds", max(duration, 0.001)))

            with self._lock:
                current = self._tasks.get(task_id)
                if not current:
                    return
                current.status = DistributedTaskStatus.COMPLETED
                current.completed_at = datetime.utcnow()
                current.result = result
                current.error = None
                if current.node_id and current.node_id in self._nodes:
                    self._release_node_resources(current, self._nodes[current.node_id])
                    current.node_id = None

                self._cache[current.cache_key] = copy.deepcopy(result)
                self._duration_samples.append(duration)
                self._baseline_samples.append(max(baseline, 1e-6))
                self._duration_samples = self._duration_samples[-200:]
                self._baseline_samples = self._baseline_samples[-200:]

            self._record_event(
                "task_completed",
                {
                    "task_id": task_id,
                    "attempt": current_attempt,
                    "duration": round(duration, 4),
                },
            )
        except Exception as exc:  # pylint: disable=broad-except
            with self._lock:
                current = self._tasks.get(task_id)
                if not current:
                    return

                if current.node_id and current.node_id in self._nodes:
                    self._release_node_resources(current, self._nodes[current.node_id])
                    current.node_id = None

                if current.attempt <= current.max_retries:
                    delay = current.retry_delay_seconds * (2 ** max(0, current.attempt - 1))
                    current.status = DistributedTaskStatus.QUEUED
                    current.error = f"执行失败，将重试: {str(exc)}"
                    current.started_at = None
                    current.next_run_at = datetime.utcnow() + timedelta(seconds=delay)
                    self._record_event(
                        "task_retry",
                        {
                            "task_id": task_id,
                            "attempt": current.attempt,
                            "next_run_in_seconds": delay,
                        },
                    )
                else:
                    current.status = DistributedTaskStatus.FAILED
                    current.completed_at = datetime.utcnow()
                    current.error = str(exc)
                    self._record_event(
                        "task_failed",
                        {
                            "task_id": task_id,
                            "attempt": current.attempt,
                            "error": str(exc),
                        },
                    )

    def _prepare_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        raw = serialized.encode("utf-8")
        raw_size = len(raw)

        if raw_size <= 4096:
            return {
                "payload": payload,
                "compressed": False,
                "payload_size": raw_size,
                "chunks": 1,
            }

        compressed = zlib.compress(raw, level=6)
        b64 = base64.b64encode(compressed).decode("ascii")
        chunk_size = 2048
        chunks = math.ceil(len(b64) / chunk_size)
        return {
            "payload": {
                "encoding": "zlib+base64",
                "chunk_size": chunk_size,
                "chunks": [b64[i : i + chunk_size] for i in range(0, len(b64), chunk_size)],
            },
            "compressed": True,
            "payload_size": raw_size,
            "chunks": chunks,
        }

    def _restore_payload(self, payload: Any, compressed: bool) -> Dict[str, Any]:
        if not compressed:
            return copy.deepcopy(payload)
        chunks = payload.get("chunks", [])
        encoded = "".join(chunks)
        data = base64.b64decode(encoded.encode("ascii"))
        raw = zlib.decompress(data)
        return json.loads(raw.decode("utf-8"))

    def _build_cache_key(self, task_type: str, payload: Dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(f"{task_type}:{normalized}".encode("utf-8")).hexdigest()

    def _run_task_logic(self, task_type: str, payload: Dict[str, Any], attempt: int) -> Dict[str, Any]:
        if task_type == "kriging_distributed":
            return self._run_kriging_distributed(payload)
        if task_type == "sampling_optimization_distributed":
            return self._run_sampling_optimization_distributed(payload)
        if task_type == "deep_learning_training_distributed":
            return self._run_deep_learning_training_distributed(payload)
        if task_type == "route_planning_distributed":
            return self._run_route_planning_distributed(payload)
        if task_type == "map_reduce_sum":
            return self._run_map_reduce_sum(payload)
        if task_type == "failing_demo":
            fail_until = int(payload.get("fail_until_attempt", 0))
            if attempt <= fail_until:
                raise RuntimeError(f"模拟失败，当前 attempt={attempt}")
            return {
                "message": "重试后成功",
                "attempt": attempt,
                "estimated_sequential_seconds": float(payload.get("estimated_sequential_seconds", 0.2)),
            }

        return {
            "echo": payload,
            "message": f"任务类型 {task_type} 已执行",
            "estimated_sequential_seconds": float(payload.get("estimated_sequential_seconds", 0.1)),
        }

    def _run_kriging_distributed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sample_points = payload.get("sample_points", [])
        sample_values = payload.get("sample_values", [])
        target_points = payload.get("target_points", [])
        power = float(payload.get("power", 2.0))

        if not sample_points or not target_points or len(sample_points) != len(sample_values):
            raise ValueError("kriging_distributed 参数无效")

        predictions: List[float] = []
        for tx, ty in target_points:
            numerator = 0.0
            denominator = 0.0
            for (sx, sy), value in zip(sample_points, sample_values):
                dx = float(tx) - float(sx)
                dy = float(ty) - float(sy)
                distance = max(math.sqrt(dx * dx + dy * dy), 1e-6)
                weight = 1.0 / (distance ** power)
                numerator += weight * float(value)
                denominator += weight
            predictions.append(numerator / denominator)

        baseline = max(0.1, len(sample_points) * len(target_points) * 0.0005)
        return {
            "prediction": predictions,
            "worker_blocks": max(1, min(8, math.ceil(len(target_points) / 16))),
            "estimated_sequential_seconds": baseline,
        }

    def _run_sampling_optimization_distributed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        candidates = payload.get("candidates", [])
        top_k = int(payload.get("top_k", 5))
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("sampling_optimization_distributed 参数无效")

        ranked = sorted(
            candidates,
            key=lambda item: (float(item.get("uncertainty", 0.0)), float(item.get("risk", 0.0))),
            reverse=True,
        )
        selected = ranked[: max(1, top_k)]
        return {
            "selected_points": selected,
            "estimated_sequential_seconds": max(0.1, len(candidates) * 0.001),
        }

    def _run_deep_learning_training_distributed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        shard_losses = payload.get("shard_losses", [])
        epochs = int(payload.get("epochs", 1))
        if not shard_losses or not isinstance(shard_losses, list):
            raise ValueError("deep_learning_training_distributed 参数无效")

        worker_means: List[float] = []
        for losses in shard_losses:
            if not losses:
                continue
            worker_means.append(sum(float(loss) for loss in losses) / len(losses))

        if not worker_means:
            raise ValueError("deep_learning_training_distributed shard_losses 为空")

        avg_loss = sum(worker_means) / len(worker_means)
        improvement = max(0.0, min(0.95, float(payload.get("improvement", 0.12))))
        final_loss = avg_loss * ((1.0 - improvement) ** max(1, epochs))

        return {
            "workers": len(worker_means),
            "initial_loss": avg_loss,
            "final_loss": final_loss,
            "estimated_sequential_seconds": max(0.2, len(worker_means) * epochs * 0.02),
        }

    def _run_route_planning_distributed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        points = payload.get("points", [])
        if not points:
            raise ValueError("route_planning_distributed 参数无效")

        remaining = [tuple(map(float, point)) for point in points]
        start = tuple(map(float, payload.get("start", remaining[0])))
        if start in remaining:
            remaining.remove(start)

        route = [start]
        current = start
        total_distance = 0.0
        while remaining:
            next_point = min(
                remaining,
                key=lambda point: math.dist(current, point),
            )
            total_distance += math.dist(current, next_point)
            route.append(next_point)
            remaining.remove(next_point)
            current = next_point

        return {
            "route": [list(point) for point in route],
            "distance": total_distance,
            "estimated_sequential_seconds": max(0.1, len(points) * 0.005),
        }

    def _run_map_reduce_sum(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        values = payload.get("values", [])
        chunk_size = max(1, int(payload.get("chunk_size", 64)))
        if not isinstance(values, list):
            raise ValueError("map_reduce_sum values 参数无效")

        partitions = [values[i : i + chunk_size] for i in range(0, len(values), chunk_size)]
        partial = [sum(float(v) for v in partition) for partition in partitions]
        total = sum(partial)
        return {
            "sum": total,
            "partitions": len(partitions),
            "estimated_sequential_seconds": max(0.05, len(values) * 0.0002),
        }

    def _record_event(self, event: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._event_log.append(
                {
                    "event": event,
                    "payload": payload,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

    def _to_task_info(self, task: _TaskState) -> DistributedTaskInfo:
        return DistributedTaskInfo(
            task_id=task.task_id,
            task_type=task.task_type,
            framework=task.framework,
            status=task.status,
            priority=task.priority,
            node_id=task.node_id,
            attempt=task.attempt,
            max_retries=task.max_retries,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error=task.error,
            result=copy.deepcopy(task.result) if task.result else None,
            resource_requirement=task.resource_requirement.model_copy(deep=True),
        )

    def _to_node_info(self, node: _NodeState) -> NodeInfoResponse:
        return NodeInfoResponse(
            node_id=node.node_id,
            status=node.status,
            cpu_capacity=node.cpu_capacity,
            memory_capacity_mb=node.memory_capacity_mb,
            cpu_used=node.cpu_used,
            memory_used=node.memory_used,
            active_tasks=len(node.active_tasks),
            labels=copy.deepcopy(node.labels),
            last_heartbeat=node.last_heartbeat,
        )

    def _serialize_task(self, task: _TaskState) -> Dict[str, Any]:
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "framework": task.framework.value,
            "status": task.status.value,
            "priority": task.priority,
            "payload": copy.deepcopy(task.payload),
            "payload_compressed": task.payload_compressed,
            "payload_size_bytes": task.payload_size_bytes,
            "payload_chunks": task.payload_chunks,
            "resource_requirement": task.resource_requirement.model_dump(),
            "max_retries": task.max_retries,
            "retry_delay_seconds": task.retry_delay_seconds,
            "attempt": task.attempt,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "next_run_at": task.next_run_at.isoformat(),
            "node_id": task.node_id,
            "error": task.error,
            "result": copy.deepcopy(task.result),
            "cache_key": task.cache_key,
        }

    def _serialize_node(self, node: _NodeState) -> Dict[str, Any]:
        return {
            "node_id": node.node_id,
            "status": node.status.value,
            "cpu_capacity": node.cpu_capacity,
            "memory_capacity_mb": node.memory_capacity_mb,
            "cpu_used": node.cpu_used,
            "memory_used": node.memory_used,
            "reserved_cpu_cores": node.reserved_cpu_cores,
            "reserved_memory_mb": node.reserved_memory_mb,
            "active_tasks": list(node.active_tasks),
            "labels": copy.deepcopy(node.labels),
            "last_heartbeat": node.last_heartbeat.isoformat(),
        }


# 全局实例
# 默认优先 Ray，不可用时自动回退 Dask，再回退本地线程池。
distributed_compute_service = DistributedComputeService(preferred_framework=DistributedFramework.RAY)
