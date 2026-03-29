"""分布式计算 API。"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.分布式计算模型 import (
    CheckpointResponse,
    ClusterOverviewResponse,
    DistributedTaskInfo,
    DistributedTaskStatus,
    DistributedTaskSubmitRequest,
    DistributedTaskSubmitResponse,
    MetricsResponse,
    NodeHeartbeatRequest,
    NodeInfoResponse,
    NodeRegisterRequest,
    RecoveryResponse,
    ScaleSuggestionResponse,
    TaskListResponse,
)
from ..services.分布式计算服务 import distributed_compute_service

router = APIRouter()


@router.post("/distributed/tasks", response_model=DistributedTaskSubmitResponse)
async def submit_distributed_task(request: DistributedTaskSubmitRequest):
    task_id = distributed_compute_service.submit_task(request)
    return DistributedTaskSubmitResponse(task_id=task_id, message="任务已提交")


@router.get("/distributed/tasks/{task_id}", response_model=DistributedTaskInfo)
async def get_distributed_task(task_id: str):
    task = distributed_compute_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/distributed/tasks", response_model=TaskListResponse)
async def list_distributed_tasks(
    status: Optional[DistributedTaskStatus] = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    tasks = distributed_compute_service.list_tasks(status=status, limit=limit)
    return TaskListResponse(tasks=tasks)


@router.delete("/distributed/tasks/{task_id}")
async def cancel_distributed_task(task_id: str):
    cancelled = distributed_compute_service.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="任务不存在或当前状态不允许取消")
    return {"task_id": task_id, "message": "任务已取消"}


@router.post("/distributed/nodes/register", response_model=NodeInfoResponse)
async def register_distributed_node(request: NodeRegisterRequest):
    return distributed_compute_service.register_node(request)


@router.post("/distributed/nodes/heartbeat", response_model=NodeInfoResponse)
async def heartbeat_distributed_node(request: NodeHeartbeatRequest):
    return distributed_compute_service.heartbeat(request)


@router.get("/distributed/nodes", response_model=List[NodeInfoResponse])
async def list_distributed_nodes():
    return distributed_compute_service.list_nodes()


@router.get("/distributed/overview", response_model=ClusterOverviewResponse)
async def get_distributed_overview():
    return distributed_compute_service.get_cluster_overview()


@router.get("/distributed/metrics", response_model=MetricsResponse)
async def get_distributed_metrics():
    return distributed_compute_service.get_metrics()


@router.get("/distributed/scale-suggestion", response_model=ScaleSuggestionResponse)
async def get_scale_suggestion():
    return distributed_compute_service.get_scale_suggestion()


@router.post("/distributed/tasks/{task_id}/checkpoint", response_model=CheckpointResponse)
async def create_task_checkpoint(task_id: str):
    try:
        return distributed_compute_service.create_checkpoint(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/distributed/tasks/{task_id}/recover", response_model=RecoveryResponse)
async def recover_distributed_task(task_id: str, checkpoint_id: Optional[str] = None):
    result = distributed_compute_service.recover_task(task_id, checkpoint_id=checkpoint_id)
    if not result.recovered:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.post("/distributed/backup")
async def backup_distributed_cluster():
    path = distributed_compute_service.backup_cluster_state()
    return {"message": "备份已生成", "path": path}


@router.post("/distributed/restore")
async def restore_distributed_cluster():
    restored = distributed_compute_service.restore_cluster_state()
    if not restored:
        raise HTTPException(status_code=404, detail="未找到可恢复备份")
    return {"message": "集群状态已恢复"}


@router.get("/distributed/events")
async def get_distributed_events(limit: int = Query(default=100, ge=1, le=500)):
    return {"events": distributed_compute_service.get_event_log(limit=limit)}
