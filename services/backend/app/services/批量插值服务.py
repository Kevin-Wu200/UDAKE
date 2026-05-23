"""
批量插值服务
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from ..schemas.批量处理模型 import (
    BatchKrigingRequest,
    BatchTaskExecutionMode,
    BatchTaskFullResponse,
)
from ..schemas.插值参数模型 import KrigingParameters
from ..schemas.输出结果模型 import TaskStatus
from ..tasks.批量任务管理器 import BatchTaskManager
from .插值计算服务 import KrigingService
from .数据预处理服务 import DataPreprocessor

logger = logging.getLogger(__name__)

class BatchKrigingService:
    """批量克里金服务"""

    def __init__(self):
        self.batch_manager = BatchTaskManager()
        self.kriging_service = KrigingService()
        self.preprocessor = DataPreprocessor()
        self.executor = ThreadPoolExecutor(max_workers=10)

    def start_batch_kriging(self, request: BatchKrigingRequest) -> BatchTaskFullResponse:
        """
        启动批量克里金任务
        """
        try:
            # 创建批量任务
            batch_id = self.batch_manager.create_batch_task(
                data_ids=request.data_ids,
                parameters=request.parameters,
                individual_parameters=request.individual_parameters,
                execution_mode=request.execution_mode,
                priority=request.priority,
                max_concurrent=request.max_concurrent,
                description=request.description
            )

            # 更新批量任务状态
            self.batch_manager.update_batch_task_status(
                batch_id,
                BatchTaskExecutionMode.RUNNING if request.execution_mode == BatchTaskExecutionMode.PARALLEL else "running",
                "批量任务已启动"
            )

            # 根据执行模式启动任务
            if request.execution_mode == BatchTaskExecutionMode.PARALLEL:
                self._execute_parallel(batch_id, request)
            else:
                self._execute_serial(batch_id, request)

            # 返回批量任务信息
            summary = self.batch_manager.get_batch_summary(batch_id)
            details = self.batch_manager.get_batch_details(batch_id)

            return BatchTaskFullResponse(
                summary=summary,
                tasks=details or []
            )

        except Exception as e:
            logger.error(f"批量任务启动失败: {str(e)}")
            raise e

    def _execute_parallel(self, batch_id: str, request: BatchKrigingRequest):
        """并行执行批量任务"""
        task_ids = self.batch_manager.batch_tasks[batch_id]["task_ids"]
        data_ids = request.data_ids
        max_concurrent = request.max_concurrent or 4

        # 创建任务队列
        task_queue = list(zip(task_ids, data_ids))

        # 使用线程池并行执行
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {}
            for task_id, data_id in task_queue:
                future = executor.submit(
                    self._execute_single_task,
                    batch_id,
                    task_id,
                    data_id,
                    request.parameters,
                    request.individual_parameters.get(data_id) if request.individual_parameters else None
                )
                futures[future] = (task_id, data_id)

            # 等待所有任务完成
            for future in as_completed(futures):
                task_id, data_id = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"任务 {task_id} (数据: {data_id}) 执行失败: {str(e)}")
                    self.batch_manager.update_task_progress(
                        batch_id,
                        task_id,
                        TaskStatus.FAILED,
                        0.0,
                        error=str(e)
                    )

    def _execute_serial(self, batch_id: str, request: BatchKrigingRequest):
        """串行执行批量任务"""
        task_ids = self.batch_manager.batch_tasks[batch_id]["task_ids"]
        data_ids = request.data_ids

        for task_id, data_id in zip(task_ids, data_ids):
            # 检查是否被暂停或取消
            batch = self.batch_manager.batch_tasks.get(batch_id, {})
            if batch.get("control_flags", {}).get("pause", False):
                # 等待恢复
                while batch.get("control_flags", {}).get("pause", False):
                    asyncio.sleep(1)
                    batch = self.batch_manager.batch_tasks.get(batch_id, {})

            if batch.get("control_flags", {}).get("cancel", False):
                break

            # 执行单个任务
            try:
                self._execute_single_task(
                    batch_id,
                    task_id,
                    data_id,
                    request.parameters,
                    request.individual_parameters.get(data_id) if request.individual_parameters else None
                )
            except Exception as e:
                logger.error(f"任务 {task_id} (数据: {data_id}) 执行失败: {str(e)}")
                self.batch_manager.update_task_progress(
                    batch_id,
                    task_id,
                    TaskStatus.FAILED,
                    0.0,
                    error=str(e)
                )

    def _execute_single_task(
        self,
        batch_id: str,
        task_id: str,
        data_id: str,
        common_params: Optional[KrigingParameters],
        individual_params: Optional[KrigingParameters]
    ):
        """执行单个克里金任务"""
        try:
            # 确定使用哪个参数
            params = individual_params if individual_params else common_params

            if not params:
                raise ValueError(f"任务 {task_id} 缺少参数")

            # 更新数据ID
            params.data_id = data_id

            # 记录任务开始时间
            self.batch_manager.record_task_start(batch_id, task_id)

            # 更新任务状态为运行中
            self.batch_manager.update_task_progress(
                batch_id,
                task_id,
                TaskStatus.RUNNING,
                0.0,
                "任务开始执行"
            )

            # 执行克里金插值
            asyncio.run(self.kriging_service.execute_kriging(task_id, params))

            # 记录任务完成时间
            self.batch_manager.record_task_completion(batch_id, task_id)

            # 更新任务状态为已完成
            self.batch_manager.update_task_progress(
                batch_id,
                task_id,
                TaskStatus.COMPLETED,
                100.0,
                "任务完成"
            )

            logger.info(f"任务 {task_id} (数据: {data_id}) 完成")

        except Exception as e:
            logger.error(f"任务 {task_id} (数据: {data_id}) 失败: {str(e)}")
            raise e

    def get_batch_status(self, batch_id: str) -> Optional[BatchTaskFullResponse]:
        """获取批量任务状态"""
        summary = self.batch_manager.get_batch_summary(batch_id)
        if not summary:
            return None

        details = self.batch_manager.get_batch_details(batch_id)

        return BatchTaskFullResponse(
            summary=summary,
            tasks=details or []
        )

    def control_batch_task(self, batch_id: str, action: str):
        """控制批量任务"""
        return self.batch_manager.control_batch_task(batch_id, action)

    def get_batch_results(self, batch_id: str):
        """获取批量任务结果"""
        return self.batch_manager.get_batch_results(batch_id)

    def get_all_batch_tasks(self) -> List[str]:
        """获取所有批量任务"""
        return self.batch_manager.get_all_batch_tasks()
