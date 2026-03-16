"""
更新策略模块
Update Strategy Module

实现多尺度更新策略和更新优先级管理
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import heapq
from datetime import datetime
import logging

from ..models import DataPoint, BoundingBox, UpdateResult

logger = logging.getLogger(__name__)


class UpdatePriority(Enum):
    """更新优先级"""
    CRITICAL = 0  # 关键更新
    HIGH = 1      # 高优先级
    MEDIUM = 2    # 中优先级
    LOW = 3       # 低优先级


class UpdateScale(Enum):
    """更新尺度"""
    LOCAL = 0     # 局部更新（小范围）
    REGIONAL = 1  # 区域更新（中等范围）
    GLOBAL = 2    # 全局更新（大范围）


@dataclass(order=True)
class UpdateTask:
    """更新任务"""
    priority: int  # 优先级（数字越小优先级越高）
    timestamp: float  # 时间戳
    point: DataPoint  # 数据点
    scale: UpdateScale  # 更新尺度
    task_id: str = field(compare=False)  # 任务ID

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().timestamp()


class MultiScaleUpdater:
    """多尺度更新器"""

    def __init__(
        self,
        local_threshold: float = 50.0,
        regional_threshold: float = 200.0,
        grid_resolution: float = 10.0
    ):
        """
        初始化多尺度更新器

        Args:
            local_threshold: 局部更新阈值（距离）
            regional_threshold: 区域更新阈值（距离）
            grid_resolution: 网格分辨率
        """
        self.local_threshold = local_threshold
        self.regional_threshold = regional_threshold
        self.grid_resolution = grid_resolution

        # 多分辨率网格
        self.local_resolution = grid_resolution
        self.regional_resolution = grid_resolution * 2
        self.global_resolution = grid_resolution * 4

    def determine_update_scale(
        self,
        new_point: DataPoint,
        existing_points: List[DataPoint],
        quadtree
    ) -> UpdateScale:
        """
        确定更新尺度

        Args:
            new_point: 新数据点
            existing_points: 已有数据点
            quadtree: 空间索引

        Returns:
            更新尺度
        """
        # 查询附近的数据点
        nearby_points = quadtree.query_radius(
            (new_point.x, new_point.y),
            self.local_threshold
        )

        # 根据附近点数和数据密度确定尺度
        density = len(nearby_points) / (np.pi * self.local_threshold ** 2)

        if density > 0.01:  # 高密度区域
            # 检查变化幅度
            if len(nearby_points) > 0:
                values = [p.value for p in nearby_points]
                value_std = np.std(values)
                value_diff = abs(new_point.value - np.mean(values))

                if value_diff > 2 * value_std:
                    # 剧烈变化，需要全局更新
                    return UpdateScale.GLOBAL
                else:
                    # 小幅变化，局部更新
                    return UpdateScale.LOCAL
            else:
                return UpdateScale.LOCAL
        elif density > 0.001:  # 中等密度
            return UpdateScale.REGIONAL
        else:  # 低密度区域
            return UpdateScale.GLOBAL

    def get_update_resolution(self, scale: UpdateScale) -> float:
        """
        获取更新尺度对应的分辨率

        Args:
            scale: 更新尺度

        Returns:
            网格分辨率
        """
        if scale == UpdateScale.LOCAL:
            return self.local_resolution
        elif scale == UpdateScale.REGIONAL:
            return self.regional_resolution
        else:
            return self.global_resolution

    def calculate_update_region(
        self,
        new_point: DataPoint,
        scale: UpdateScale
    ) -> BoundingBox:
        """
        计算更新区域

        Args:
            new_point: 新数据点
            scale: 更新尺度

        Returns:
            更新区域边界框
        """
        # 根据尺度确定更新半径
        if scale == UpdateScale.LOCAL:
            radius = self.local_threshold
        elif scale == UpdateScale.REGIONAL:
            radius = self.regional_threshold
        else:
            # 全局更新使用更大的半径
            radius = self.regional_threshold * 2

        # 计算分辨率
        resolution = self.get_update_resolution(scale)

        # 确定边界
        min_x = new_point.x - radius
        max_x = new_point.x + radius
        min_y = new_point.y - radius
        max_y = new_point.y + radius

        # 对齐到网格
        min_x = np.floor(min_x / resolution) * resolution
        max_x = np.ceil(max_x / resolution) * resolution
        min_y = np.floor(min_y / resolution) * resolution
        max_y = np.ceil(max_y / resolution) * resolution

        return BoundingBox(min_x, max_x, min_y, max_y)


class UpdatePriorityManager:
    """更新优先级管理器"""

    def __init__(
        self,
        max_queue_size: int = 1000,
        aging_factor: float = 0.1
    ):
        """
        初始化优先级管理器

        Args:
            max_queue_size: 最大队列大小
            aging_factor: 老化因子
        """
        self.max_queue_size = max_queue_size
        self.aging_factor = aging_factor
        self.task_queue: List[UpdateTask] = []
        self.task_counter = 0

    def add_task(
        self,
        point: DataPoint,
        scale: UpdateScale,
        priority: UpdatePriority = UpdatePriority.MEDIUM
    ) -> str:
        """
        添加更新任务

        Args:
            point: 数据点
            scale: 更新尺度
            priority: 优先级

        Returns:
            任务ID
        """
        # 检查队列大小
        if len(self.task_queue) >= self.max_queue_size:
            logger.warning(f"任务队列已满，丢弃最旧的任务")
            heapq.heappop(self.task_queue)

        # 创建任务
        self.task_counter += 1
        task = UpdateTask(
            priority=priority.value,
            timestamp=datetime.now().timestamp(),
            point=point,
            scale=scale,
            task_id=f"task_{self.task_counter}"
        )

        # 添加到队列
        heapq.heappush(self.task_queue, task)

        return task.task_id

    def get_next_task(self) -> Optional[UpdateTask]:
        """
        获取下一个任务

        Returns:
            下一个任务，如果没有则返回None
        """
        if not self.task_queue:
            return None

        task = heapq.heappop(self.task_queue)

        # 应用老化因子
        age = datetime.now().timestamp() - task.timestamp
        task.priority += int(age * self.aging_factor)

        return task

    def peek_next_task(self) -> Optional[UpdateTask]:
        """
        查看下一个任务（不删除）

        Returns:
            下一个任务，如果没有则返回None
        """
        if not self.task_queue:
            return None
        return self.task_queue[0]

    def get_queue_size(self) -> int:
        """获取队列大小"""
        return len(self.task_queue)

    def clear_queue(self) -> None:
        """清空队列"""
        self.task_queue.clear()

    def update_task_priority(self, task_id: str, new_priority: UpdatePriority) -> bool:
        """
        更新任务优先级

        Args:
            task_id: 任务ID
            new_priority: 新优先级

        Returns:
            是否更新成功
        """
        # 查找任务
        for i, task in enumerate(self.task_queue):
            if task.task_id == task_id:
                # 更新优先级
                self.task_queue[i].priority = new_priority.value
                # 重新堆化
                heapq.heapify(self.task_queue)
                return True

        return False


class BatchUpdateManager:
    """批量更新管理器"""

    def __init__(
        self,
        batch_size: int = 10,
        max_wait_time: float = 1.0,
        max_merge_distance: float = 100.0
    ):
        """
        初始化批量更新管理器

        Args:
            batch_size: 批量大小
            max_wait_time: 最大等待时间（秒）
            max_merge_distance: 最大合并距离
        """
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time
        self.max_merge_distance = max_merge_distance

        self.pending_tasks: List[UpdateTask] = []
        self.last_flush_time = datetime.now().timestamp()

    def add_task(self, task: UpdateTask) -> None:
        """添加任务"""
        self.pending_tasks.append(task)

    def should_flush(self) -> bool:
        """
        检查是否应该刷新队列

        Returns:
            是否应该刷新
        """
        # 检查批量大小
        if len(self.pending_tasks) >= self.batch_size:
            return True

        # 检查等待时间
        current_time = datetime.now().timestamp()
        if current_time - self.last_flush_time >= self.max_wait_time:
            return True

        return False

    def flush(self) -> List[UpdateTask]:
        """
        刷新队列，返回批量任务

        Returns:
            批量任务列表
        """
        # 合并相邻任务
        merged_tasks = self._merge_tasks()

        # 清空队列
        tasks_to_return = merged_tasks.copy()
        self.pending_tasks.clear()
        self.last_flush_time = datetime.now().timestamp()

        return tasks_to_return

    def _merge_tasks(self) -> List[UpdateTask]:
        """
        合并相邻任务

        Returns:
            合并后的任务列表
        """
        if not self.pending_tasks:
            return []

        # 按时间排序
        sorted_tasks = sorted(self.pending_tasks, key=lambda t: t.timestamp)

        merged = []
        current_group = [sorted_tasks[0]]

        for task in sorted_tasks[1:]:
            # 检查是否可以合并
            can_merge = False
            for group_task in current_group:
                distance = np.sqrt(
                    (task.point.x - group_task.point.x) ** 2 +
                    (task.point.y - group_task.point.y) ** 2
                )
                if distance <= self.max_merge_distance:
                    can_merge = True
                    break

            if can_merge:
                current_group.append(task)
            else:
                # 不能合并，创建批量任务
                merged.append(self._create_batch_task(current_group))
                current_group = [task]

        # 添加最后一组
        if current_group:
            merged.append(self._create_batch_task(current_group))

        return merged

    def _create_batch_task(self, tasks: List[UpdateTask]) -> UpdateTask:
        """
        创建批量任务

        Args:
            tasks: 任务列表

        Returns:
            批量任务
        """
        # 计算中心点
        avg_x = np.mean([t.point.x for t in tasks])
        avg_y = np.mean([t.point.y for t in tasks])
        avg_value = np.mean([t.point.value for t in tasks])

        # 确定最大尺度
        max_scale = max(t.scale for t in tasks)

        # 创建批量点
        batch_point = DataPoint(
            x=avg_x,
            y=avg_y,
            value=avg_value,
            id=f"batch_{len(tasks)}"
        )

        # 使用最高优先级
        min_priority = min(t.priority for t in tasks)

        return UpdateTask(
            priority=min_priority,
            timestamp=min(t.timestamp for t in tasks),
            point=batch_point,
            scale=max_scale,
            task_id=f"batch_{datetime.now().timestamp()}"
        )


class ThrottleController:
    """更新节流控制器"""

    def __init__(
        self,
        max_updates_per_second: float = 10.0,
        burst_size: int = 5
    ):
        """
        初始化节流控制器

        Args:
            max_updates_per_second: 每秒最大更新数
            burst_size: 突发大小
        """
        self.max_updates_per_second = max_updates_per_second
        self.burst_size = burst_size

        self.update_times: List[float] = []
        self.token_bucket = burst_size
        self.last_refill_time = datetime.now().timestamp()

    def should_allow_update(self) -> bool:
        """
        检查是否允许更新

        Returns:
            是否允许
        """
        current_time = datetime.now().timestamp()

        # 补充令牌
        self._refill_tokens(current_time)

        # 检查令牌
        if self.token_bucket >= 1:
            self.token_bucket -= 1
            self.update_times.append(current_time)
            return True
        else:
            return False

    def _refill_tokens(self, current_time: float) -> None:
        """补充令牌"""
        elapsed = current_time - self.last_refill_time
        tokens_to_add = elapsed * self.max_updates_per_second

        self.token_bucket = min(
            self.burst_size,
            self.token_bucket + tokens_to_add
        )

        self.last_refill_time = current_time

    def get_update_rate(self) -> float:
        """
        获取当前更新率

        Returns:
            每秒更新数
        """
        current_time = datetime.now().timestamp()

        # 清理旧的时间戳
        self.update_times = [
            t for t in self.update_times
            if current_time - t < 1.0
        ]

        return len(self.update_times)


def test_multi_scale_updater():
    """测试多尺度更新器"""
    print("\n测试多尺度更新器...")

    from ..index.quadtree import QuadTree

    # 创建多尺度更新器
    updater = MultiScaleUpdater()

    # 创建空间索引
    boundary = BoundingBox(0, 1000, 0, 1000)
    quadtree = QuadTree(boundary)

    # 添加一些数据点
    for i in range(50):
        point = DataPoint(
            x=np.random.uniform(400, 600),
            y=np.random.uniform(400, 600),
            value=np.random.randn(),
            id=f"point_{i}"
        )
        quadtree.insert(point)

    # 测试新点
    new_point = DataPoint(
        x=500,
        y=500,
        value=10.0,
        id="new_point"
    )

    scale = updater.determine_update_scale(new_point, [], quadtree)
    print(f"更新尺度: {scale}")

    resolution = updater.get_update_resolution(scale)
    print(f"网格分辨率: {resolution}")

    region = updater.calculate_update_region(new_point, scale)
    print(f"更新区域: ({region.min_x:.2f}, {region.max_x:.2f}) x "
          f"({region.min_y:.2f}, {region.max_y:.2f})")

    print("多尺度更新器测试通过！")


def test_update_priority_manager():
    """测试更新优先级管理器"""
    print("\n测试更新优先级管理器...")

    manager = UpdatePriorityManager()

    # 添加任务
    for i in range(10):
        point = DataPoint(
            x=np.random.uniform(0, 100),
            y=np.random.uniform(0, 100),
            value=np.random.randn(),
            id=f"point_{i}"
        )
        priority = UpdatePriority.HIGH if i % 3 == 0 else UpdatePriority.MEDIUM
        task_id = manager.add_task(point, UpdateScale.LOCAL, priority)
        print(f"添加任务: {task_id}")

    # 获取任务
    print(f"\n队列大小: {manager.get_queue_size()}")
    task = manager.get_next_task()
    print(f"获取任务: {task.task_id}, 优先级: {task.priority}")

    print("更新优先级管理器测试通过！")


def test_batch_update_manager():
    """测试批量更新管理器"""
    print("\n测试批量更新管理器...")

    manager = BatchUpdateManager(batch_size=5)

    # 添加任务
    for i in range(12):
        point = DataPoint(
            x=np.random.uniform(0, 100),
            y=np.random.uniform(0, 100),
            value=np.random.randn(),
            id=f"point_{i}"
        )
        task = UpdateTask(
            priority=UpdatePriority.MEDIUM.value,
            timestamp=datetime.now().timestamp(),
            point=point,
            scale=UpdateScale.LOCAL,
            task_id=f"task_{i}"
        )
        manager.add_task(task)

    # 检查是否应该刷新
    should_flush = manager.should_flush()
    print(f"是否应该刷新: {should_flush}")

    # 刷新队列
    if should_flush:
        batch_tasks = manager.flush()
        print(f"批量任务数: {len(batch_tasks)}")

    print("批量更新管理器测试通过！")


def test_throttle_controller():
    """测试节流控制器"""
    print("\n测试节流控制器...")

    controller = ThrottleController(max_updates_per_second=10.0)

    # 尝试更新
    allowed_count = 0
    for i in range(15):
        if controller.should_allow_update():
            allowed_count += 1
            print(f"更新 {i+1}: 允许")
        else:
            print(f"更新 {i+1}: 被节流")

    print(f"\n允许的更新数: {allowed_count}")
    print(f"当前更新率: {controller.get_update_rate():.2f} /s")

    print("节流控制器测试通过！")


if __name__ == "__main__":
    test_multi_scale_updater()
    test_update_priority_manager()
    test_batch_update_manager()
    test_throttle_controller()
    print("\n所有测试通过！")