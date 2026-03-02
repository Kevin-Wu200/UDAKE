"""
报告生成接口
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from ..schemas.输出结果模型 import KrigingReport
from ..services.报告生成服务 import ReportGenerator
from ..dependencies import verify_task_id

router = APIRouter()
report_generator = ReportGenerator()

@router.get("/result/report/{task_id}", response_model=KrigingReport)
async def get_report(task_id: str = Depends(verify_task_id)):
    """
    生成并获取克里金分析报告
    """
    try:
        report = report_generator.generate_report(task_id)
        if not report:
            raise HTTPException(status_code=404, detail="报告生成失败")
        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")
