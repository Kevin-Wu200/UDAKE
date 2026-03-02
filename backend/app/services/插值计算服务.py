"""
插值计算服务
"""
from ..schemas.插值参数模型 import KrigingParameters
from ..services.数据预处理服务 import DataPreprocessor
from ..core.克里金调度器 import KrigingScheduler
from ..tasks.任务管理器 import TaskManager
from ..schemas.输出结果模型 import TaskStatus
import logging

logger = logging.getLogger(__name__)

class KrigingService:
    """克里金计算服务"""

    def __init__(self):
        self.preprocessor = DataPreprocessor()
        self.scheduler = KrigingScheduler()
        self.task_manager = TaskManager()

    async def execute_kriging(self, task_id: str, params: KrigingParameters):
        """
        执行克里金插值
        """
        try:
            # 更新任务状态
            self.task_manager.update_task_status(task_id, TaskStatus.RUNNING, 0.0)

            # 加载数据
            spatial_data = self.preprocessor.load_data(params.data_id)
            logger.info(f"任务 {task_id}: 数据加载完成，点数: {len(spatial_data.points)}")

            # 执行插值
            result = self.scheduler.execute(
                task_id=task_id,
                spatial_data=spatial_data,
                params=params
            )

            # 更新任务状态
            self.task_manager.update_task_status(task_id, TaskStatus.COMPLETED, 100.0)
            self.task_manager.save_result(task_id, result)

            logger.info(f"任务 {task_id}: 完成")

        except Exception as e:
            logger.error(f"任务 {task_id} 失败: {str(e)}")
            self.task_manager.update_task_status(
                task_id,
                TaskStatus.FAILED,
                0.0,
                error=str(e)
            )
