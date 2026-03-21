"""
插值任务接口
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from ..schemas.插值参数模型 import KrigingParameters, TaskStartResponse
from ..tasks.任务管理器 import TaskManager
from ..services.插值计算服务 import KrigingService
import uuid

router = APIRouter()
task_manager = TaskManager()
kriging_service = KrigingService()

@router.post("/start-kriging", response_model=TaskStartResponse)
async def start_kriging(
    params: KrigingParameters,
    background_tasks: BackgroundTasks
):
    """
    启动克里金插值任务
    """
    try:
        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务
        task_manager.create_task(task_id, params)

        # 添加后台任务
        background_tasks.add_task(
            kriging_service.execute_kriging,
            task_id,
            params
        )

        return TaskStartResponse(
            task_id=task_id,
            status="pending",
            message="克里金任务已启动"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"任务启动失败: {str(e)}")
