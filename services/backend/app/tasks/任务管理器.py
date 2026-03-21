"""
任务管理器
"""
from ..schemas.输出结果模型 import TaskStatus, TaskStatusResponse, PredictionResult, VarianceResult
from ..schemas.插值参数模型 import KrigingParameters
from ..schemas.进度详情模型 import ProgressDetail, ProgressStage, StageInfo, BlockProgress
from datetime import datetime
from typing import Dict, Optional, Any, List
import threading

class TaskManager:
    """任务管理器"""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self.__class__._initialized:
            return
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self.progress_details: Dict[str, ProgressDetail] = {}
        self.lock = threading.Lock()
        self.__class__._initialized = True

    def reset(self):
        """重置任务状态（测试用）"""
        with self.lock:
            self.tasks.clear()
            self.results.clear()
            self.progress_details.clear()

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
            # 初始化进度详情
            self.progress_details[task_id] = ProgressDetail(
                task_id=task_id,
                current_stage=None,
                overall_progress=0.0,
                stages=[],
                block_progress=None,
                estimated_total_time=None,
                estimated_remaining_time=None,
                elapsed_time=0.0
            )

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

    def initialize_progress_stages(self, task_id: str, stages: List[ProgressStage]):
        """初始化进度阶段"""
        with self.lock:
            if task_id in self.progress_details:
                stage_infos = []
                stage_names = {
                    ProgressStage.DATA_LOADING: "数据加载",
                    ProgressStage.DATA_VALIDATION: "数据验证",
                    ProgressStage.VARIOGRAM_FITTING: "变异函数拟合",
                    ProgressStage.INTERPOLATION: "插值计算",
                    ProgressStage.CROSS_VALIDATION: "交叉验证",
                    ProgressStage.RESULT_GENERATION: "结果生成",
                    ProgressStage.EXPORTING: "结果导出",
                    ProgressStage.COMPLETED: "完成"
                }
                for stage in stages:
                    stage_infos.append(StageInfo(
                        stage=stage,
                        stage_name=stage_names.get(stage, str(stage)),
                        progress=0.0,
                        status="pending"
                    ))
                self.progress_details[task_id].stages = stage_infos

    def update_stage_progress(
        self,
        task_id: str,
        stage: ProgressStage,
        progress: float,
        status: Optional[str] = None,
        message: Optional[str] = None
    ):
        """更新阶段进度"""
        with self.lock:
            if task_id in self.progress_details:
                progress_detail = self.progress_details[task_id]
                for stage_info in progress_detail.stages:
                    if stage_info.stage == stage:
                        stage_info.progress = progress
                        if status:
                            stage_info.status = status
                        if message:
                            stage_info.message = message

                        # 更新开始和完成时间
                        if status == "running" and stage_info.started_at is None:
                            stage_info.started_at = datetime.now()
                        if status == "completed" and stage_info.completed_at is None:
                            stage_info.completed_at = datetime.now()
                            if stage_info.started_at:
                                stage_info.duration = (
                                    stage_info.completed_at - stage_info.started_at
                                ).total_seconds()

                # 更新当前阶段
                progress_detail.current_stage = stage
                progress_detail.updated_at = datetime.now()

                # 计算总体进度
                self._calculate_overall_progress(task_id)

    def update_block_progress(
        self,
        task_id: str,
        current_block: int,
        total_blocks: int,
        processed_blocks: int,
        processing_speed: Optional[float] = None
    ):
        """更新分块处理进度"""
        with self.lock:
            if task_id in self.progress_details:
                block_progress = BlockProgress(
                    current_block=current_block,
                    total_blocks=total_blocks,
                    processed_blocks=processed_blocks,
                    processing_speed=processing_speed
                )

                # 计算预计剩余时间
                if processing_speed and processing_speed > 0:
                    remaining_blocks = total_blocks - processed_blocks
                    block_progress.estimated_remaining_time = remaining_blocks / processing_speed

                self.progress_details[task_id].block_progress = block_progress
                self.progress_details[task_id].updated_at = datetime.now()

    def update_elapsed_time(self, task_id: str, elapsed_time: float):
        """更新已用时间"""
        with self.lock:
            if task_id in self.progress_details:
                self.progress_details[task_id].elapsed_time = elapsed_time
                self.progress_details[task_id].updated_at = datetime.now()

    def _calculate_overall_progress(self, task_id: str):
        """计算总体进度"""
        if task_id in self.progress_details:
            progress_detail = self.progress_details[task_id]
            if not progress_detail.stages:
                return

            total_progress = sum(
                stage.progress for stage in progress_detail.stages
            )
            overall_progress = total_progress / len(progress_detail.stages)
            progress_detail.overall_progress = overall_progress

    def get_progress_detail(self, task_id: str) -> Optional[ProgressDetail]:
        """获取进度详情"""
        with self.lock:
            if task_id not in self.progress_details:
                return None
            return self.progress_details[task_id]

    def calculate_estimated_remaining_time(self, task_id: str) -> Optional[float]:
        """计算预计剩余时间"""
        with self.lock:
            if task_id not in self.progress_details:
                return None

            progress_detail = self.progress_details[task_id]

            # 基于分块进度计算
            if progress_detail.block_progress and progress_detail.block_progress.estimated_remaining_time:
                return progress_detail.block_progress.estimated_remaining_time

            # 基于已用时间和总体进度计算
            if progress_detail.elapsed_time and progress_detail.overall_progress > 0:
                estimated_total = progress_detail.elapsed_time / (progress_detail.overall_progress / 100)
                return max(0, estimated_total - progress_detail.elapsed_time)

            return None
