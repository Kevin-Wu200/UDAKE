"""
批量插值接口
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from ..schemas.批量处理模型 import (
    BatchKrigingRequest, BatchTaskStartResponse, BatchTaskFullResponse,
    BatchTaskControlRequest, BatchTaskControlResponse, BatchTaskResultsSummary
)
from ..services.批量插值服务 import BatchKrigingService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
batch_kriging_service = BatchKrigingService()

@router.post("/api/batch-kriging", response_model=BatchTaskStartResponse)
async def start_batch_kriging(request: BatchKrigingRequest):
    """
    启动批量克里金插值任务

    参数说明：
    - data_ids: 数据ID列表
    - parameters: 统一参数（可选）
    - individual_parameters: 单独参数字典（可选，键为数据ID）
    - execution_mode: 执行模式（serial/parallel）
    - priority: 任务优先级（low/medium/high）
    - max_concurrent: 最大并发任务数（仅并行模式有效）
    - description: 任务描述（可选）
    """
    try:
        # 验证请求参数
        if not request.data_ids:
            raise HTTPException(status_code=400, detail="数据ID列表不能为空")

        if not request.parameters and not request.individual_parameters:
            raise HTTPException(status_code=400, detail="必须提供统一参数或单独参数")

        # 启动批量任务
        response = batch_kriging_service.start_batch_kriging(request)

        batch_id = response.summary.batch_id

        logger.info(f"批量克里金任务已启动: {batch_id}, 任务数: {len(request.data_ids)}")

        return BatchTaskStartResponse(
            batch_id=batch_id,
            status=response.summary.status,
            message="批量克里金任务已启动",
            total_tasks=response.summary.total_tasks,
            estimated_duration=response.summary.estimated_remaining_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量克里金任务启动失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"任务启动失败: {str(e)}")


@router.get("/api/batch-kriging/{batch_id}/status", response_model=BatchTaskFullResponse)
async def get_batch_status(batch_id: str):
    """
    获取批量任务状态

    参数说明：
    - batch_id: 批量任务ID
    """
    try:
        response = batch_kriging_service.get_batch_status(batch_id)

        if not response:
            raise HTTPException(status_code=404, detail="批量任务不存在")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取批量任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/api/batch-kriging/{batch_id}/control", response_model=BatchTaskControlResponse)
async def control_batch_task(batch_id: str, request: BatchTaskControlRequest):
    """
    控制批量任务（暂停/恢复/取消）

    参数说明：
    - batch_id: 批量任务ID
    - action: 操作类型（pause/resume/cancel）
    """
    try:
        # 验证操作类型
        valid_actions = ["pause", "resume", "cancel"]
        if request.action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"无效的操作类型: {request.action}，必须为 {valid_actions} 之一"
            )

        response = batch_kriging_service.control_batch_task(batch_id, request.action)

        if not response:
            raise HTTPException(status_code=404, detail="批量任务不存在")

        logger.info(f"批量任务控制: {batch_id}, 操作: {request.action}, 结果: {response.status}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"控制批量任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"控制任务失败: {str(e)}")


@router.get("/api/batch-kriging/{batch_id}/results", response_model=BatchTaskResultsSummary)
async def get_batch_results(batch_id: str):
    """
    获取批量任务结果

    参数说明：
    - batch_id: 批量任务ID
    """
    try:
        results = batch_kriging_service.get_batch_results(batch_id)

        if not results:
            raise HTTPException(status_code=404, detail="批量任务不存在")

        # 计算统计信息
        successful_tasks = sum(1 for r in results if r["status"] == "completed")
        failed_tasks = sum(1 for r in results if r["status"] == "failed")
        total_tasks = len(results)
        success_rate = (successful_tasks / total_tasks) * 100 if total_tasks > 0 else 0

        # 收集所有结果
        all_results = [r["result"] for r in results if r["result"]]

        # 计算统计指标
        statistics = {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": success_rate,
            "has_results": len(all_results) > 0
        }

        if all_results:
            # 计算交叉验证指标的统计
            cv_metrics = []
            for result in all_results:
                if "cross_validation" in result:
                    cv_metrics.append(result["cross_validation"])

            if cv_metrics:
                rmse_values = [m.get("rmse") for m in cv_metrics if m.get("rmse") is not None]
                mae_values = [m.get("mae") for m in cv_metrics if m.get("mae") is not None]
                r2_values = [m.get("r2") for m in cv_metrics if m.get("r2") is not None]

                if rmse_values:
                    statistics["rmse"] = {
                        "min": min(rmse_values),
                        "max": max(rmse_values),
                        "mean": sum(rmse_values) / len(rmse_values),
                        "std": (sum((x - sum(rmse_values) / len(rmse_values)) ** 2 for x in rmse_values) / len(rmse_values)) ** 0.5
                    }

                if mae_values:
                    statistics["mae"] = {
                        "min": min(mae_values),
                        "max": max(mae_values),
                        "mean": sum(mae_values) / len(mae_values),
                        "std": (sum((x - sum(mae_values) / len(mae_values)) ** 2 for x in mae_values) / len(mae_values)) ** 0.5
                    }

                if r2_values:
                    statistics["r2"] = {
                        "min": min(r2_values),
                        "max": max(r2_values),
                        "mean": sum(r2_values) / len(r2_values),
                        "std": (sum((x - sum(r2_values) / len(r2_values)) ** 2 for x in r2_values) / len(r2_values)) ** 0.5
                    }

        from datetime import datetime

        return BatchTaskResultsSummary(
            batch_id=batch_id,
            total_tasks=total_tasks,
            successful_tasks=successful_tasks,
            failed_tasks=failed_tasks,
            success_rate=success_rate,
            results=all_results,
            statistics=statistics,
            generated_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取批量任务结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取结果失败: {str(e)}")


@router.get("/api/batch-kriging")
async def list_batch_tasks():
    """
    列出所有批量任务

    返回所有批量任务的ID列表
    """
    try:
        batch_ids = batch_kriging_service.get_all_batch_tasks()

        return {
            "batch_ids": batch_ids,
            "total": len(batch_ids)
        }

    except Exception as e:
        logger.error(f"列出批量任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"列出任务失败: {str(e)}")