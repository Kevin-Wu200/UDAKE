"""
报告生成服务
"""
from datetime import datetime
from typing import Optional

from ..schemas.输出结果模型 import CrossValidationMetrics, KrigingReport
from ..tasks.任务管理器 import TaskManager


class ReportGenerator:
    """报告生成器"""

    def __init__(self):
        self.task_manager = TaskManager()

    def generate_report(self, task_id: str) -> Optional[KrigingReport]:
        """
        生成克里金分析报告
        """
        # 获取任务信息
        task_info = self.task_manager.get_task_info(task_id)
        if not task_info:
            return None

        # 获取结果
        prediction_result = self.task_manager.get_prediction_result(task_id)
        variance_result = self.task_manager.get_variance_result(task_id)

        if not prediction_result or not variance_result:
            return None

        # 构建报告
        report = KrigingReport(
            task_id=task_id,
            method=task_info.get("method", "ordinary"),
            variogram_model=task_info.get("variogram_model", "spherical"),
            point_count=task_info.get("point_count", 0),
            grid_resolution=task_info.get("grid_resolution", 100),
            cross_validation=self._get_cv_metrics(task_info),
            prediction_stats=prediction_result.statistics,
            variance_stats=variance_result.statistics,
            execution_time=task_info.get("execution_time", 0.0),
            generated_at=datetime.now()
        )

        return report

    def _get_cv_metrics(self, task_info: dict) -> Optional[CrossValidationMetrics]:
        """获取交叉验证指标"""
        cv_data = task_info.get("cross_validation")
        if not cv_data:
            return None

        return CrossValidationMetrics(
            rmse=cv_data.get("rmse", 0.0),
            mae=cv_data.get("mae", 0.0),
            r2=cv_data.get("r2", 0.0),
            mse=cv_data.get("mse", 0.0)
        )
