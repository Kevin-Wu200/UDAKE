"""
结果查询接口
"""
from fastapi import APIRouter, HTTPException, Depends
from ..schemas.输出结果模型 import PredictionResult, VarianceResult
from ..tasks.任务管理器 import TaskManager
from ..dependencies import verify_task_id

router = APIRouter()
task_manager = TaskManager()

@router.get("/result/prediction/{task_id}", response_model=PredictionResult)
async def get_prediction_result(task_id: str = Depends(verify_task_id)):
    """
    获取预测结果
    """
    try:
        result = task_manager.get_prediction_result(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="结果不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

@router.get("/result/variance/{task_id}", response_model=VarianceResult)
async def get_variance_result(task_id: str = Depends(verify_task_id)):
    """
    获取方差结果
    """
    try:
        result = task_manager.get_variance_result(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="结果不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
