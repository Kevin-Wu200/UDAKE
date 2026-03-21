"""
结果对比分析接口
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from ..schemas.批量处理模型 import ResultComparisonResponse
from ..services.结果对比分析服务 import ResultComparisonService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
result_comparison_service = ResultComparisonService()


@router.get("/api/batch-kriging/{batch_id}/comparison", response_model=ResultComparisonResponse)
async def get_batch_comparison(batch_id: str):
    """
    获取批量任务结果对比

    参数说明：
    - batch_id: 批量任务ID

    返回所有任务的交叉验证指标对比，包括：
    - RMSE 对比
    - MAE 对比
    - R² 对比
    - MSE 对比
    - 执行时间对比
    - 最佳和最差结果
    - 统计信息
    """
    try:
        comparison = result_comparison_service.compare_batch_results(batch_id)

        if not comparison:
            raise HTTPException(status_code=404, detail="批量任务不存在或没有已完成的结果")

        return comparison

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取批量任务对比失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取对比失败: {str(e)}")


@router.get("/api/batch-kriging/{batch_id}/ranking")
async def get_results_ranking(
    batch_id: str,
    metric: str = "rmse",
    ascending: bool = True
):
    """
    根据指定指标对结果进行排名

    参数说明：
    - batch_id: 批量任务ID
    - metric: 排序指标（rmse/mae/r2/mse/execution_time）
    - ascending: 是否升序排列（默认为 True）
    """
    try:
        # 验证指标类型
        valid_metrics = ["rmse", "mae", "r2", "mse", "execution_time"]
        if metric not in valid_metrics:
            raise HTTPException(
                status_code=400,
                detail=f"无效的排序指标: {metric}，必须为 {valid_metrics} 之一"
            )

        ranked_results = result_comparison_service.rank_results_by_metric(
            batch_id,
            metric,
            ascending
        )

        if not ranked_results:
            raise HTTPException(status_code=404, detail="批量任务不存在或没有已完成的结果")

        return {
            "batch_id": batch_id,
            "metric": metric,
            "ascending": ascending,
            "ranked_results": ranked_results,
            "total": len(ranked_results)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取结果排名失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取排名失败: {str(e)}")


@router.get("/api/batch-kriging/{batch_id}/difference")
async def get_result_difference(batch_id: str, task_id_1: str, task_id_2: str):
    """
    比较两个任务的差异

    参数说明：
    - batch_id: 批量任务ID
    - task_id_1: 任务ID 1
    - task_id_2: 任务ID 2
    """
    try:
        difference = result_comparison_service.get_result_difference(
            batch_id,
            task_id_1,
            task_id_2
        )

        if not difference:
            raise HTTPException(
                status_code=404,
                detail="批量任务不存在或任务ID无效"
            )

        return difference

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取结果差异失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取差异失败: {str(e)}")


@router.get("/api/batch-kriging/{batch_id}/comparison/export", response_class=PlainTextResponse)
async def export_comparison_csv(batch_id: str):
    """
    导出对比结果为 CSV 格式

    参数说明：
    - batch_id: 批量任务ID

    返回 CSV 格式的对比结果，包含所有任务的指标和排名
    """
    try:
        csv_content = result_comparison_service.export_comparison_to_csv(batch_id)

        if not csv_content:
            raise HTTPException(status_code=404, detail="批量任务不存在或没有已完成的结果")

        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=batch_{batch_id}_comparison.csv"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出对比结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/api/batch-kriging/{batch_id}/comparison/statistics")
async def get_comparison_statistics(batch_id: str):
    """
    获取对比结果的统计信息

    参数说明：
    - batch_id: 批量任务ID

    返回各项指标的统计信息，包括：
    - 最小值、最大值、平均值、中位数、标准差
    """
    try:
        comparison = result_comparison_service.compare_batch_results(batch_id)

        if not comparison:
            raise HTTPException(status_code=404, detail="批量任务不存在或没有已完成的结果")

        return {
            "batch_id": batch_id,
            "statistics": comparison.statistics,
            "best_result": comparison.best_result,
            "worst_result": comparison.worst_result,
            "total_tasks": len(comparison.metrics)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对比统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/api/batch-kriging/{batch_id}/comparison/summary")
async def get_comparison_summary(batch_id: str):
    """
    获取对比结果的摘要信息

    参数说明：
    - batch_id: 批量任务ID

    返回一个简化的摘要，包含关键信息
    """
    try:
        comparison = result_comparison_service.compare_batch_results(batch_id)

        if not comparison:
            raise HTTPException(status_code=404, detail="批量任务不存在或没有已完成的结果")

        # 生成摘要
        summary = {
            "batch_id": batch_id,
            "total_tasks": len(comparison.metrics),
            "average_rmse": None,
            "average_mae": None,
            "average_r2": None,
            "best_task": None,
            "worst_task": None
        }

        # 计算平均值
        rmse_values = [m.rmse for m in comparison.metrics if m.rmse is not None]
        if rmse_values:
            summary["average_rmse"] = sum(rmse_values) / len(rmse_values)

        mae_values = [m.mae for m in comparison.metrics if m.mae is not None]
        if mae_values:
            summary["average_mae"] = sum(mae_values) / len(mae_values)

        r2_values = [m.r2 for m in comparison.metrics if m.r2 is not None]
        if r2_values:
            summary["average_r2"] = sum(r2_values) / len(r2_values)

        # 最佳和最差任务
        if comparison.best_result:
            summary["best_task"] = {
                "task_id": comparison.best_result["task_id"],
                "data_id": comparison.best_result["data_id"],
                "rmse": comparison.best_result["rmse"]
            }

        if comparison.worst_result:
            summary["worst_task"] = {
                "task_id": comparison.worst_result["task_id"],
                "data_id": comparison.worst_result["data_id"],
                "rmse": comparison.worst_result["rmse"]
            }

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对比摘要失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取摘要失败: {str(e)}")