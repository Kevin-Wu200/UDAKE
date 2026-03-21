"""
克里金调度器
"""
from ..schemas.数据模型 import SpatialData
from ..schemas.插值参数模型 import KrigingParameters, KrigingMethod
from ..core.普通克里金引擎 import OrdinaryKrigingEngine
from ..core.泛克里金引擎 import UniversalKrigingEngine
from ..core.分块克里金引擎 import BlockKrigingEngine
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class KrigingScheduler:
    """克里金调度器"""

    def __init__(self):
        self.engines = {
            KrigingMethod.ORDINARY: OrdinaryKrigingEngine(),
            KrigingMethod.UNIVERSAL: UniversalKrigingEngine(),
            KrigingMethod.BLOCK: BlockKrigingEngine()
        }

    def execute(
        self,
        task_id: str,
        spatial_data: SpatialData,
        params: KrigingParameters
    ) -> Dict[str, Any]:
        """
        执行克里金插值
        """
        # 选择引擎
        engine = self.engines.get(params.method)
        if not engine:
            raise ValueError(f"不支持的克里金方法: {params.method}")

        logger.info(f"任务 {task_id}: 使用 {params.method} 方法")

        # 执行插值
        result = engine.interpolate(
            task_id=task_id,
            spatial_data=spatial_data,
            params=params
        )

        return result
