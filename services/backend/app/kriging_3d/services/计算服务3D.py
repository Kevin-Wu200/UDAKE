"""
3D克里金计算服务
"""
import json
import logging
from typing import Any, Dict, Optional

import numpy as np

from ...config import settings
from ..core.调度器3D import KrigingScheduler3D
from ..schemas.参数模型 import KrigingParameters3D, SliceParams
from ..schemas.结果模型 import TaskStatus3D
from ..services.数据处理3D import DataProcessor3D

logger = logging.getLogger(__name__)


class Kriging3DService:
    """3D克里金计算服务"""

    def __init__(self):
        self.processor = DataProcessor3D()
        self.scheduler = KrigingScheduler3D()
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}

    async def execute_kriging_3d(self, task_id: str, params: KrigingParameters3D):
        """执行3D克里金插值任务"""
        try:
            self.tasks[task_id] = {"status": TaskStatus3D.RUNNING, "progress": 0.0}

            # 加载数据
            spatial_data = self.processor.load_data(params.data_id)
            logger.info(f"3D任务 {task_id}: 数据加载完成, 点数={len(spatial_data.points)}")
            self.tasks[task_id]["progress"] = 10.0

            # 数据预处理
            spatial_data = self.processor.clean_data(spatial_data)
            self.tasks[task_id]["progress"] = 20.0

            # 执行插值
            result = self.scheduler.execute(task_id, spatial_data, params)
            self.tasks[task_id]["progress"] = 90.0

            # 保存结果
            self._save_result(task_id, result)
            self.results[task_id] = result

            # 计算统计信息
            pred_key = "prediction" if "prediction" in result else "probability"
            pred_data = result[pred_key]
            var_data = result["variance"]

            self.tasks[task_id] = {
                "status": TaskStatus3D.COMPLETED,
                "progress": 100.0,
                "grid_shape": result.get("grid_shape"),
                "prediction_stats": self._compute_stats(pred_data),
                "variance_stats": self._compute_stats(var_data),
                "variogram": result.get("variogram"),
            }
            logger.info(f"3D任务 {task_id}: 完成")

        except Exception as e:
            logger.error(f"3D任务 {task_id} 失败: {str(e)}")
            self.tasks[task_id] = {
                "status": TaskStatus3D.FAILED,
                "progress": 0.0,
                "error": str(e)
            }

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        if task_id not in self.tasks:
            return {"status": "not_found"}
        return self.tasks[task_id]

    def get_slice(self, task_id: str, slice_params: SliceParams) -> Optional[Dict[str, Any]]:
        """获取3D结果的切片"""
        if task_id not in self.results:
            return None

        result = self.results[task_id]
        pred_key = "prediction" if "prediction" in result else "probability"
        pred_data = result[pred_key]
        var_data = result["variance"]
        grid_x = np.array(result["grid_x"])
        grid_y = np.array(result["grid_y"])
        grid_z = np.array(result["grid_z"])

        axis = slice_params.axis.lower()
        pos = slice_params.position

        if axis == "z":
            idx = np.argmin(np.abs(grid_z - pos))
            return {
                "axis": "z", "position": float(grid_z[idx]),
                "grid_x": grid_x.tolist(), "grid_y": grid_y.tolist(),
                "values": pred_data[:, :, idx].tolist(),
                "variance": var_data[:, :, idx].tolist(),
            }
        elif axis == "x":
            idx = np.argmin(np.abs(grid_x - pos))
            return {
                "axis": "x", "position": float(grid_x[idx]),
                "grid_x": grid_y.tolist(), "grid_y": grid_z.tolist(),
                "values": pred_data[idx, :, :].tolist(),
                "variance": var_data[idx, :, :].tolist(),
            }
        elif axis == "y":
            idx = np.argmin(np.abs(grid_y - pos))
            return {
                "axis": "y", "position": float(grid_y[idx]),
                "grid_x": grid_x.tolist(), "grid_y": grid_z.tolist(),
                "values": pred_data[:, idx, :].tolist(),
                "variance": var_data[:, idx, :].tolist(),
            }
        return None

    def export_result(self, task_id: str, format: str = "json") -> Optional[str]:
        """导出3D结果"""
        if task_id not in self.results:
            return None

        result = self.results[task_id]
        export_dir = settings.RESULTS_DIR / "3d"
        export_dir.mkdir(parents=True, exist_ok=True)

        if format == "json":
            path = export_dir / f"{task_id}_3d_result.json"
            export_data = {
                "task_id": task_id,
                "grid_x": result["grid_x"],
                "grid_y": result["grid_y"],
                "grid_z": result["grid_z"],
                "grid_shape": result.get("grid_shape"),
                "method": result.get("method"),
                "variogram": result.get("variogram"),
            }
            # 将numpy数组转为列表
            pred_key = "prediction" if "prediction" in result else "probability"
            export_data["prediction"] = result[pred_key].tolist()
            export_data["variance"] = result["variance"].tolist()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False)
            return str(path)

        elif format == "npz":
            path = export_dir / f"{task_id}_3d_result.npz"
            pred_key = "prediction" if "prediction" in result else "probability"
            np.savez_compressed(
                path,
                prediction=result[pred_key],
                variance=result["variance"],
                grid_x=np.array(result["grid_x"]),
                grid_y=np.array(result["grid_y"]),
                grid_z=np.array(result["grid_z"]),
            )
            return str(path)

        return None

    def _save_result(self, task_id: str, result: Dict[str, Any]):
        """保存结果到文件"""
        save_dir = settings.RESULTS_DIR / "3d"
        save_dir.mkdir(parents=True, exist_ok=True)
        path = save_dir / f"{task_id}_3d_cache.npz"
        pred_key = "prediction" if "prediction" in result else "probability"
        np.savez_compressed(
            path,
            prediction=result[pred_key],
            variance=result["variance"],
            grid_x=np.array(result["grid_x"]),
            grid_y=np.array(result["grid_y"]),
            grid_z=np.array(result["grid_z"]),
        )

    def _compute_stats(self, data: np.ndarray) -> Dict[str, float]:
        """计算统计信息"""
        return {
            "mean": float(np.mean(data)),
            "std": float(np.std(data)),
            "min": float(np.min(data)),
            "max": float(np.max(data)),
            "median": float(np.median(data)),
            "count": int(data.size),
        }
