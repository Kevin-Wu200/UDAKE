"""
任务管理器
"""
from ..schemas.输出结果模型 import TaskStatus, TaskStatusResponse, PredictionResult, VarianceResult
from ..schemas.插值参数模型 import KrigingParameters
from datetime import datetime
from typing import Dict, Optional, Any
import threading

class TaskManager:
    """任务管理器"""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def create_task(self, task_id: str, params: KrigingParameters):
        """创建任务"""
        with self.lock:
            self.tasks[task_id] = {
                "task_id": task_id,
                "status": TaskStatus.PENDING,
                "progress": 0.0,
                "message": "任务已创建",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "params": params.model_dump(),
                "error": None
            }

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: float,
        message: Optional[str] = None,
        error: Optional[str] = None
    ):
        """更新任务状态"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = status
                self.tasks[task_id]["progress"] = progress
                self.tasks[task_id]["updated_at"] = datetime.now()
                if message:
                    self.tasks[task_id]["message"] = message
                if error:
                    self.tasks[task_id]["error"] = error

    def get_task_status(self, task_id: str) -> Optional[TaskStatusResponse]:
        """获取任务状态"""
        with self.lock:
            if task_id not in self.tasks:
                return None

            task = self.tasks[task_id]
            return TaskStatusResponse(
                task_id=task_id,
                status=task["status"],
                progress=task["progress"],
                message=task.get("message"),
                created_at=task["created_at"],
                updated_at=task["updated_at"],
                error=task.get("error")
            )

    def save_result(self, task_id: str, result: Dict[str, Any]):
        """保存结果"""
        with self.lock:
            self.results[task_id] = result

    def get_prediction_result(self, task_id: str) -> Optional[PredictionResult]:
        """获取预测结果"""
        with self.lock:
            if task_id not in self.results:
                return None

            result = self.results[task_id]
            return PredictionResult(
                task_id=task_id,
                geotiff_url=f"/results/{task_id}_prediction.tif",
                geojson_url=f"/results/{task_id}_prediction.geojson",
                shapefile_url=f"/results/{task_id}_prediction.shp",
                statistics=result.get("prediction_stats", {})
            )

    def get_variance_result(self, task_id: str) -> Optional[VarianceResult]:
        """获取方差结果"""
        with self.lock:
            if task_id not in self.results:
                return None

            result = self.results[task_id]
            return VarianceResult(
                task_id=task_id,
                geotiff_url=f"/results/{task_id}_variance.tif",
                geojson_url=f"/results/{task_id}_variance.geojson",
                shapefile_url=f"/results/{task_id}_variance.shp",
                statistics=result.get("variance_stats", {})
            )

    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务完整信息"""
        with self.lock:
            if task_id not in self.tasks:
                return None

            task = self.tasks[task_id].copy()
            if task_id in self.results:
                task.update(self.results[task_id])

            return task
