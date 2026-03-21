"""
任务状态接口
"""
from fastapi import APIRouter, HTTPException, Depends
from ..schemas.输出结果模型 import TaskStatusResponse
from ..tasks.任务管理器 import TaskManager
from ..dependencies import verify_task_id

router = APIRouter()
task_manager = TaskManager()

@router.get("/task-status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str = Depends(verify_task_id)):
    """
    查询任务状态
    """
    try:
        status = task_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="任务不存在")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
