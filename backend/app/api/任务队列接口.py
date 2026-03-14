"""
任务队列接口
"""
from fastapi import APIRouter, HTTPException
from ..schemas.任务队列模型 import (
    QueueTaskInfo, QueueTaskStatus, QueueTaskPriority,
    QueueStatistics, QueueVisualization, TaskControlRequest,
    TaskControlResponse, TaskPriorityUpdateRequest,
    BatchTaskControlRequest, BatchTaskControlResponse,
    QueueConfig
)
from ..services.任务队列管理器 import task_queue_manager
from typing import List, Optional

router = APIRouter()

@router.post("/queue/tasks", response_model=dict)
async def add_task(
    task_type: str,
    parameters: dict,
    priority: QueueTaskPriority = QueueTaskPriority.MEDIUM,
    metadata: Optional[dict] = None
):
    """
    添加任务到队列
    """
    try:
        task_id = task_queue_manager.add_task(
            task_type=task_type,
            parameters=parameters,
            priority=priority,
            metadata=metadata or {}
        )
        return {
            "task_id": task_id,
            "message": "任务已添加到队列"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/queue/tasks/{task_id}", response_model=QueueTaskInfo)
async def get_task(task_id: str):
    """
    获取任务信息
    """
    task = task_queue_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

@router.get("/queue/tasks", response_model=List[QueueTaskInfo])
async def get_all_tasks(status: Optional[QueueTaskStatus] = None):
    """
    获取所有任务
    """
    return task_queue_manager.get_all_tasks(status)

@router.post("/queue/tasks/control", response_model=TaskControlResponse)
async def control_task(request: TaskControlRequest):
    """
    控制任务
    """
    result = task_queue_manager.control_task(request.task_id, request.action)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.message)
    return result

@router.post("/queue/tasks/batch-control")
async def batch_control_tasks(request: BatchTaskControlRequest):
    """
    批量控制任务
    """
    result = task_queue_manager.batch_control_tasks(request.task_ids, request.action)
    return result

@router.put("/queue/tasks/{task_id}/priority")
async def update_task_priority(task_id: str, request: TaskPriorityUpdateRequest):
    """
    更新任务优先级
    """
    success = task_queue_manager.update_task_priority(task_id, request.priority)
    if not success:
        raise HTTPException(status_code=400, detail="更新失败，任务不存在或状态不允许")
    return {
        "task_id": task_id,
        "priority": request.priority,
        "message": "优先级已更新"
    }

@router.get("/queue/statistics", response_model=QueueStatistics)
async def get_statistics():
    """
    获取队列统计信息
    """
    return task_queue_manager.get_statistics()

@router.get("/queue/visualization", response_model=QueueVisualization)
async def get_visualization():
    """
    获取队列可视化数据
    """
    return task_queue_manager.get_visualization()

@router.get("/queue/config", response_model=QueueConfig)
async def get_queue_config():
    """
    获取队列配置
    """
    return task_queue_manager.get_config()

@router.put("/queue/config")
async def update_queue_config(config: QueueConfig):
    """
    更新队列配置
    """
    task_queue_manager.update_config(config)
    return {
        "message": "配置已更新",
        "config": config
    }

@router.delete("/queue/tasks/completed")
async def clear_completed_tasks():
    """
    清除已完成的任务
    """
    task_queue_manager.clear_completed_tasks()
    return {"message": "已完成的任务已清除"}

@router.delete("/queue/history")
async def clear_history():
    """
    清除历史记录
    """
    task_queue_manager.clear_history()
    return {"message": "历史记录已清除"}

@router.post("/queue/start")
async def start_queue():
    """
    启动队列管理器
    """
    task_queue_manager.start()
    return {"message": "队列管理器已启动"}

@router.post("/queue/stop")
async def stop_queue():
    """
    停止队列管理器
    """
    task_queue_manager.stop()
    return {"message": "队列管理器已停止"}