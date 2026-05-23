"""
进度详情接口
"""
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import verify_task_id
from ..schemas.进度详情模型 import ProgressDetail, ProgressStage
from ..tasks.任务管理器 import TaskManager

router = APIRouter()
task_manager = TaskManager()

@router.get("/progress-detail/{task_id}", response_model=ProgressDetail)
async def get_progress_detail(task_id: str = Depends(verify_task_id)):
    """
    获取任务进度详情
    """
    try:
        progress_detail = task_manager.get_progress_detail(task_id)
        if not progress_detail:
            raise HTTPException(status_code=404, detail="任务不存在")
        return progress_detail
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

@router.get("/estimated-remaining-time/{task_id}")
async def get_estimated_remaining_time(task_id: str = Depends(verify_task_id)):
    """
    获取预计剩余时间
    """
    try:
        remaining_time = task_manager.calculate_estimated_remaining_time(task_id)
        if remaining_time is None:
            raise HTTPException(status_code=404, detail="无法计算剩余时间")
        return {
            "task_id": task_id,
            "estimated_remaining_time": remaining_time,
            "estimated_remaining_time_formatted": f"{int(remaining_time // 60)}分{int(remaining_time % 60)}秒"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

@router.get("/stage-progress/{task_id}/{stage}")
async def get_stage_progress(task_id: str = Depends(verify_task_id), stage: ProgressStage = None):
    """
    获取特定阶段的进度
    """
    try:
        progress_detail = task_manager.get_progress_detail(task_id)
        if not progress_detail:
            raise HTTPException(status_code=404, detail="任务不存在")

        for stage_info in progress_detail.stages:
            if stage_info.stage == stage:
                return {
                    "task_id": task_id,
                    "stage": stage,
                    "stage_name": stage_info.stage_name,
                    "progress": stage_info.progress,
                    "status": stage_info.status,
                    "message": stage_info.message,
                    "started_at": stage_info.started_at,
                    "completed_at": stage_info.completed_at,
                    "duration": stage_info.duration
                }

        raise HTTPException(status_code=404, detail="阶段不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
