"""
结果对比分析服务
"""
from ..schemas.批量处理模型 import (
    ResultComparisonMetrics, ResultComparisonResponse
)
from ..tasks.批量任务管理器 import BatchTaskManager
from ..tasks.任务管理器 import TaskManager
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)

class ResultComparisonService:
    """结果对比分析服务"""

    def __init__(self):
        self.batch_manager = BatchTaskManager()
        self.task_manager = TaskManager()

    def compare_batch_results(self, batch_id: str) -> Optional[ResultComparisonResponse]:
        """
        对比批量任务结果

        参数说明：
        - batch_id: 批量任务ID
        """
        try:
            # 获取批量任务结果
            batch_results = self.batch_manager.get_batch_results(batch_id)

            if not batch_results:
                logger.warning(f"批量任务 {batch_id} 没有结果")
                return None

            # 提取对比指标
            metrics = []
            for result in batch_results:
                if result["status"] != "completed":
                    continue

                task_id = result["task_id"]
                data_id = result["data_id"]
                result_data = result["result"]

                # 提取交叉验证指标
                cv_metrics = result_data.get("cross_validation", {})
                prediction_stats = result_data.get("prediction_stats", {})

                metric = ResultComparisonMetrics(
                    task_id=task_id,
                    data_id=data_id,
                    rmse=cv_metrics.get("rmse"),
                    mae=cv_metrics.get("mae"),
                    r2=cv_metrics.get("r2"),
                    mse=cv_metrics.get("mse"),
                    execution_time=result_data.get("execution_time"),
                    point_count=prediction_stats.get("count", 0)
                )

                metrics.append(metric)

            if not metrics:
                logger.warning(f"批量任务 {batch_id} 没有已完成的任务")
                return None

            # 计算统计信息
            statistics = self._calculate_statistics(metrics)

            # 识别最佳和最差结果
            best_result = self._find_best_result(metrics)
            worst_result = self._find_worst_result(metrics)

            return ResultComparisonResponse(
                batch_id=batch_id,
                metrics=metrics,
                statistics=statistics,
                best_result=best_result,
                worst_result=worst_result,
                generated_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"对比批量任务结果失败: {str(e)}")
            raise e

    def _calculate_statistics(self, metrics: List[ResultComparisonMetrics]) -> Dict[str, Any]:
        """计算统计信息"""
        stats = {}

        # RMSE 统计
        rmse_values = [m.rmse for m in metrics if m.rmse is not None]
        if rmse_values:
            stats["rmse"] = {
                "min": min(rmse_values),
                "max": max(rmse_values),
                "mean": statistics.mean(rmse_values),
                "median": statistics.median(rmse_values),
                "stdev": statistics.stdev(rmse_values) if len(rmse_values) > 1 else 0
            }

        # MAE 统计
        mae_values = [m.mae for m in metrics if m.mae is not None]
        if mae_values:
            stats["mae"] = {
                "min": min(mae_values),
                "max": max(mae_values),
                "mean": statistics.mean(mae_values),
                "median": statistics.median(mae_values),
                "stdev": statistics.stdev(mae_values) if len(mae_values) > 1 else 0
            }

        # R² 统计
        r2_values = [m.r2 for m in metrics if m.r2 is not None]
        if r2_values:
            stats["r2"] = {
                "min": min(r2_values),
                "max": max(r2_values),
                "mean": statistics.mean(r2_values),
                "median": statistics.median(r2_values),
                "stdev": statistics.stdev(r2_values) if len(r2_values) > 1 else 0
            }

        # MSE 统计
        mse_values = [m.mse for m in metrics if m.mse is not None]
        if mse_values:
            stats["mse"] = {
                "min": min(mse_values),
                "max": max(mse_values),
                "mean": statistics.mean(mse_values),
                "median": statistics.median(mse_values),
                "stdev": statistics.stdev(mse_values) if len(mse_values) > 1 else 0
            }

        # 执行时间统计
        exec_times = [m.execution_time for m in metrics if m.execution_time is not None]
        if exec_times:
            stats["execution_time"] = {
                "min": min(exec_times),
                "max": max(exec_times),
                "mean": statistics.mean(exec_times),
                "median": statistics.median(exec_times),
                "stdev": statistics.stdev(exec_times) if len(exec_times) > 1 else 0
            }

        # 数据点统计
        point_counts = [m.point_count for m in metrics if m.point_count is not None]
        if point_counts:
            stats["point_count"] = {
                "min": min(point_counts),
                "max": max(point_counts),
                "mean": statistics.mean(point_counts),
                "median": statistics.median(point_counts),
                "total": sum(point_counts)
            }

        return stats

    def _find_best_result(self, metrics: List[ResultComparisonMetrics]) -> Optional[Dict[str, Any]]:
        """识别最佳结果（基于 RMSE 最小）"""
        valid_metrics = [m for m in metrics if m.rmse is not None]

        if not valid_metrics:
            return None

        best = min(valid_metrics, key=lambda m: m.rmse)

        return {
            "task_id": best.task_id,
            "data_id": best.data_id,
            "rmse": best.rmse,
            "mae": best.mae,
            "r2": best.r2,
            "mse": best.mse,
            "execution_time": best.execution_time,
            "point_count": best.point_count
        }

    def _find_worst_result(self, metrics: List[ResultComparisonMetrics]) -> Optional[Dict[str, Any]]:
        """识别最差结果（基于 RMSE 最大）"""
        valid_metrics = [m for m in metrics if m.rmse is not None]

        if not valid_metrics:
            return None

        worst = max(valid_metrics, key=lambda m: m.rmse)

        return {
            "task_id": worst.task_id,
            "data_id": worst.data_id,
            "rmse": worst.rmse,
            "mae": worst.mae,
            "r2": worst.r2,
            "mse": worst.mse,
            "execution_time": worst.execution_time,
            "point_count": worst.point_count
        }

    def rank_results_by_metric(
        self,
        batch_id: str,
        metric: str = "rmse",
        ascending: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        根据指定指标对结果进行排名

        参数说明：
        - batch_id: 批量任务ID
        - metric: 排序指标（rmse/mae/r2/mse/execution_time）
        - ascending: 是否升序排列
        """
        try:
            comparison = self.compare_batch_results(batch_id)

            if not comparison:
                return None

            # 按指定指标排序
            ranked_metrics = sorted(
                comparison.metrics,
                key=lambda m: getattr(m, metric, float('inf')) if getattr(m, metric, None) is not None else float('inf'),
                reverse=not ascending
            )

            # 生成排名结果
            ranked_results = []
            for rank, metric_obj in enumerate(ranked_metrics, start=1):
                ranked_results.append({
                    "rank": rank,
                    "task_id": metric_obj.task_id,
                    "data_id": metric_obj.data_id,
                    metric: getattr(metric_obj, metric),
                    "rmse": metric_obj.rmse,
                    "mae": metric_obj.mae,
                    "r2": metric_obj.r2,
                    "mse": metric_obj.mse,
                    "execution_time": metric_obj.execution_time,
                    "point_count": metric_obj.point_count
                })

            return ranked_results

        except Exception as e:
            logger.error(f"结果排名失败: {str(e)}")
            raise e

    def get_result_difference(
        self,
        batch_id: str,
        task_id_1: str,
        task_id_2: str
    ) -> Optional[Dict[str, Any]]:
        """
        比较两个任务的差异

        参数说明：
        - batch_id: 批量任务ID
        - task_id_1: 任务ID 1
        - task_id_2: 任务ID 2
        """
        try:
            comparison = self.compare_batch_results(batch_id)

            if not comparison:
                return None

            # 查找两个任务
            metric_1 = next((m for m in comparison.metrics if m.task_id == task_id_1), None)
            metric_2 = next((m for m in comparison.metrics if m.task_id == task_id_2), None)

            if not metric_1 or not metric_2:
                return None

            # 计算差异
            differences = {
                "task_id_1": task_id_1,
                "data_id_1": metric_1.data_id,
                "task_id_2": task_id_2,
                "data_id_2": metric_2.data_id,
                "rmse_difference": None,
                "mae_difference": None,
                "r2_difference": None,
                "mse_difference": None,
                "execution_time_difference": None,
                "point_count_difference": None,
                "better_task": None
            }

            # 计算各项指标差异
            if metric_1.rmse is not None and metric_2.rmse is not None:
                differences["rmse_difference"] = metric_1.rmse - metric_2.rmse

            if metric_1.mae is not None and metric_2.mae is not None:
                differences["mae_difference"] = metric_1.mae - metric_2.mae

            if metric_1.r2 is not None and metric_2.r2 is not None:
                differences["r2_difference"] = metric_1.r2 - metric_2.r2

            if metric_1.mse is not None and metric_2.mse is not None:
                differences["mse_difference"] = metric_1.mse - metric_2.mse

            if metric_1.execution_time is not None and metric_2.execution_time is not None:
                differences["execution_time_difference"] = metric_1.execution_time - metric_2.execution_time

            if metric_1.point_count is not None and metric_2.point_count is not None:
                differences["point_count_difference"] = metric_1.point_count - metric_2.point_count

            # 判断哪个任务更好（基于 RMSE）
            if metric_1.rmse is not None and metric_2.rmse is not None:
                if metric_1.rmse < metric_2.rmse:
                    differences["better_task"] = task_id_1
                elif metric_2.rmse < metric_1.rmse:
                    differences["better_task"] = task_id_2
                else:
                    differences["better_task"] = "equal"

            return differences

        except Exception as e:
            logger.error(f"获取结果差异失败: {str(e)}")
            raise e

    def export_comparison_to_csv(self, batch_id: str) -> Optional[str]:
        """
        将对比结果导出为 CSV 格式

        参数说明：
        - batch_id: 批量任务ID
        """
        try:
            comparison = self.compare_batch_results(batch_id)

            if not comparison:
                return None

            # 生成 CSV 内容
            csv_lines = []
            csv_lines.append("Rank,Task ID,Data ID,RMSE,MAE,R²,MSE,Execution Time,Point Count")

            for rank, metric in enumerate(comparison.metrics, start=1):
                csv_lines.append(
                    f"{rank},{metric.task_id},{metric.data_id},"
                    f"{metric.rmse if metric.rmse else ''},"
                    f"{metric.mae if metric.mae else ''},"
                    f"{metric.r2 if metric.r2 else ''},"
                    f"{metric.mse if metric.mse else ''},"
                    f"{metric.execution_time if metric.execution_time else ''},"
                    f"{metric.point_count if metric.point_count else ''}"
                )

            return "\n".join(csv_lines)

        except Exception as e:
            logger.error(f"导出对比结果失败: {str(e)}")
            raise e