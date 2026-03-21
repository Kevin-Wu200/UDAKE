"""
插值结果存储服务
提供插值结果的存储和检索功能
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class InterpolationResultStorage:
    """插值结果存储服务（内存存储，生产环境应使用数据库）"""
    
    _instance = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.results: Dict[str, Dict[str, Any]] = {}
            logger.info("创建插值结果存储单例")
        return cls._instance
    
    def __init__(self):
        # 不要在这里初始化 results，在 __new__ 中初始化
        pass
    
    def save_result(
        self,
        interpolation_id: str,
        grid: list,
        variance: list,
        bounds: dict,
        cellSize: float,
        statistics: dict
    ) -> None:
        """
        保存插值结果
        
        Args:
            interpolation_id: 插值任务ID
            grid: 预测栅格数据
            variance: 方差栅格数据
            bounds: 边界信息
            cellSize: 单元格大小
            statistics: 统计信息
        """
        self.results[interpolation_id] = {
            'grid': grid,
            'variance': variance,
            'bounds': bounds,
            'cellSize': cellSize,
            'statistics': statistics
        }
        logger.info(f"已保存插值结果: {interpolation_id}, 当前存储结果数: {len(self.results)}")
    
    def get_result(self, interpolation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取插值结果
        
        Args:
            interpolation_id: 插值任务ID
            
        Returns:
            插值结果字典，如果不存在则返回None
        """
        result = self.results.get(interpolation_id)
        if result:
            logger.debug(f"获取插值结果: {interpolation_id}")
        else:
            logger.warning(f"插值结果不存在: {interpolation_id}")
        return result
    
    def delete_result(self, interpolation_id: str) -> bool:
        """
        删除插值结果
        
        Args:
            interpolation_id: 插值任务ID
            
        Returns:
            是否删除成功
        """
        if interpolation_id in self.results:
            del self.results[interpolation_id]
            logger.info(f"已删除插值结果: {interpolation_id}")
            return True
        return False
    
    def clear_all(self) -> None:
        """清除所有结果"""
        self.results.clear()
        logger.info("已清除所有插值结果")


def get_interpolation_storage() -> InterpolationResultStorage:
    """获取插值结果存储单例"""
    return InterpolationResultStorage()