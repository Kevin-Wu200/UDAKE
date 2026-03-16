"""
增量克里金插值算法
Incremental Kriging Interpolation

实现基于Sherman-Morrison公式的增量克里金插值
"""

import numpy as np
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import logging

from ..models import (
    DataPoint, BoundingBox, VariogramModel,
    UpdateResult, Subscription
)
from ..index.quadtree import QuadTree
from ..config import KrigingConfig
from .matrix_update import ShermanMorrisonUpdater, WoodburyUpdater

logger = logging.getLogger(__name__)


class IncrementalKriging:
    """增量克里金插值器"""

    def __init__(
        self,
        subscription: Subscription,
        config: Optional[KrigingConfig] = None
    ):
        """
        初始化增量克里金插值器

        Args:
            subscription: 订阅信息
            config: 克里金配置
        """
        self.subscription = subscription
        self.config = config or KrigingConfig()

        # 初始化变异函数模型
        variogram_params = subscription.interpolation_params.get(
            'variogram_model',
            {'model_type': 'spherical', 'sill': 1.0, 'range': 100.0, 'nugget': 0.1}
        )
        self.variogram = VariogramModel(**variogram_params)

        # 初始化空间索引
        self.quadtree = QuadTree(subscription.spatial_extent)

        # 协方差矩阵及其逆
        self.covariance_matrix: Optional[np.ndarray] = None
        self.covariance_matrix_inv: Optional[np.ndarray] = None

        # 数据点列表
        self.data_points: List[DataPoint] = []

        # 网格参数
        self.grid_resolution = subscription.interpolation_params.get('grid_resolution', 100)

        # 版本号
        self.version = 0

        # 更新计数
        self.update_count = 0

        # 矩阵更新器
        self.sherman_morrison = ShermanMorrisonUpdater(self.config.epsilon)
        self.woodbury = WoodburyUpdater(self.config.epsilon)

    def add_initial_points(self, points: List[DataPoint]) -> None:
        """
        添加初始数据点

        Args:
            points: 初始数据点列表
        """
        for point in points:
            self.quadtree.insert(point)
            self.data_points.append(point)

        # 初始化协方差矩阵
        self._initialize_covariance_matrix()

        logger.info(f"添加了 {len(points)} 个初始数据点")

    def _initialize_covariance_matrix(self) -> None:
        """初始化协方差矩阵"""
        n = len(self.data_points)

        if n == 0:
            return

        # 计算协方差矩阵
        K = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                K[i, j] = self.variogram.covariance(self.data_points[i], self.data_points[j])

        self.covariance_matrix = K

        # 计算逆矩阵
        try:
            self.covariance_matrix_inv = np.linalg.inv(K)
        except np.linalg.LinAlgError as e:
            logger.error(f"协方差矩阵不可逆: {e}")
            raise

    def incremental_update(self, new_point: DataPoint) -> UpdateResult:
        """
        增量更新插值结果

        Args:
            new_point: 新数据点

        Returns:
            更新结果
        """
        start_time = datetime.now()

        # 检查是否需要重计算
        if (self.config.enable_incremental and
            self.update_count >= self.config.max_updates_before_recalc):

            logger.info(f"达到最大更新次数 {self.update_count}，执行重计算")
            self._recalculate()
            self.update_count = 0

        # 插入新点到空间索引
        self.quadtree.insert(new_point)

        # 计算影响域
        influence_domain = self._calculate_influence_domain(new_point)

        # 执行增量更新
        if self.config.enable_incremental and self.covariance_matrix_inv is not None:
            self._incremental_update_matrix(new_point)
        else:
            self._full_update()

        # 更新数据点列表
        self.data_points.append(new_point)

        # 生成更新结果
        update_result = self._generate_update_result(
            new_point, influence_domain, start_time
        )

        self.update_count += 1
        self.version += 1

        logger.info(f"增量更新完成，版本号: {self.version}")

        return update_result

    def _calculate_influence_domain(self, new_point: DataPoint) -> BoundingBox:
        """
        计算影响域

        Args:
            new_point: 新数据点

        Returns:
            影响域边界框
        """
        # 基于变异函数的变程计算影响半径
        range_radius = self.variogram.range * self.config.influence_radius_multiplier

        # 限制影响半径范围
        range_radius = max(
            self.config.min_influence_radius,
            min(self.config.max_influence_radius, range_radius)
        )

        # 考虑数据密度调整半径
        nearby_points = self.quadtree.query_radius(
            (new_point.x, new_point.y), range_radius
        )

        if len(nearby_points) > 0:
            # 如果附近有数据点，调整影响半径
            distances = [
                np.sqrt((point.x - new_point.x)**2 + (point.y - new_point.y)**2)
                for point in nearby_points
            ]
            avg_distance = np.mean(distances)
            influence_radius = min(range_radius, avg_distance * 2)
        else:
            influence_radius = range_radius

        # 确定影响域边界
        min_x = new_point.x - influence_radius
        max_x = new_point.x + influence_radius
        min_y = new_point.y - influence_radius
        max_y = new_point.y + influence_radius

        # 对齐到网格
        min_x = np.floor(min_x / self.grid_resolution) * self.grid_resolution
        max_x = np.ceil(max_x / self.grid_resolution) * self.grid_resolution
        min_y = np.floor(min_y / self.grid_resolution) * self.grid_resolution
        max_y = np.ceil(max_y / self.grid_resolution) * self.grid_resolution

        return BoundingBox(min_x, max_x, min_y, max_y)

    def _incremental_update_matrix(self, new_point: DataPoint) -> None:
        """
        使用Sherman-Morrison公式增量更新协方差矩阵

        Args:
            new_point: 新数据点
        """
        if self.covariance_matrix_inv is None:
            return

        n = len(self.data_points)

        # 计算新点与已有点的协方差向量
        k_new = np.array([
            self.variogram.covariance(new_point, point)
            for point in self.data_points
        ])

        # 计算新点的自协方差
        c_new = self.variogram.covariance(new_point, new_point)

        # 使用Sherman-Morrison公式更新
        self.covariance_matrix_inv = self.sherman_morrison.add_row_col(
            self.covariance_matrix_inv,
            k_new,
            c_new
        )

    def _full_update(self) -> None:
        """全量更新协方差矩阵"""
        self._initialize_covariance_matrix()

    def _recalculate(self) -> None:
        """重计算整个协方差矩阵"""
        logger.info("开始重计算协方差矩阵...")
        self._full_update()
        logger.info("重计算完成")

    def _generate_update_result(
        self,
        new_point: DataPoint,
        influence_domain: BoundingBox,
        start_time: datetime
    ) -> UpdateResult:
        """
        生成更新结果

        Args:
            new_point: 新数据点
            influence_domain: 影响域
            start_time: 开始时间

        Returns:
            更新结果
        """
        # 计算影响域内的预测栅格
        prediction_grid, variance_grid = self._compute_prediction_grid(influence_domain)

        # 计算统计信息
        end_time = datetime.now()
        update_time_ms = (end_time - start_time).total_seconds() * 1000

        # 计算影响域内的点数
        affected_points = self.quadtree.query_range(influence_domain)

        statistics = {
            'update_time_ms': update_time_ms,
            'affected_points': len(affected_points),
            'cache_hit_rate': 0.0  # 暂时设为0，后续集成缓存系统后更新
        }

        return UpdateResult(
            update_id=f"update_{self.version}",
            subscription_id=self.subscription.subscription_id,
            timestamp=datetime.now(),
            update_type="incremental" if self.config.enable_incremental else "full",
            affected_region=influence_domain,
            prediction_grid=prediction_grid,
            variance_grid=variance_grid,
            version=self.version,
            statistics=statistics
        )

    def _compute_prediction_grid(
        self,
        domain: BoundingBox
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算预测栅格

        Args:
            domain: 计算域

        Returns:
            (预测值栅格, 方差栅格)
        """
        # 生成网格点
        x_coords = np.arange(domain.min_x, domain.max_x, self.grid_resolution)
        y_coords = np.arange(domain.min_y, domain.max_y, self.grid_resolution)

        nx = len(x_coords)
        ny = len(y_coords)

        # 初始化栅格
        prediction_grid = np.zeros((ny, nx))
        variance_grid = np.zeros((ny, nx))

        # 对每个网格点进行插值
        for i, y in enumerate(y_coords):
            for j, x in enumerate(x_coords):
                pred, var = self._interpolate_at_point(x, y)
                prediction_grid[i, j] = pred
                variance_grid[i, j] = var

        return prediction_grid, variance_grid

    def _interpolate_at_point(self, x: float, y: float) -> Tuple[float, float]:
        """
        在指定点进行插值

        Args:
            x: X坐标
            y: Y坐标

        Returns:
            (预测值, 方差)
        """
        if len(self.data_points) == 0:
            return 0.0, 0.0

        # 计算预测点与已知点的协方差向量
        k = np.array([
            self.variogram.covariance(
                DataPoint(x=x, y=y, value=0, id="temp"),
                point
            )
            for point in self.data_points
        ])

        # 计算权重
        if self.covariance_matrix_inv is not None:
            weights = self.covariance_matrix_inv @ k
        else:
            weights = np.zeros(len(self.data_points))

        # 计算预测值
        prediction = np.sum(weights * np.array([p.value for p in self.data_points]))

        # 计算方差
        variance = self.variogram.covariance(
            DataPoint(x=x, y=y, value=0, id="temp"),
            DataPoint(x=x, y=y, value=0, id="temp")
        ) - np.sum(weights * k)

        return prediction, max(0.0, variance)

    def batch_incremental_update(self, new_points: List[DataPoint]) -> List[UpdateResult]:
        """
        批量增量更新

        Args:
            new_points: 新数据点列表

        Returns:
            更新结果列表
        """
        results = []

        # 合并相邻的影响域
        influence_domains = [
            self._calculate_influence_domain(point)
            for point in new_points
        ]

        # 逐个更新（简化实现，可以使用Woodbury优化）
        for point in new_points:
            result = self.incremental_update(point)
            results.append(result)

        return results


def test_incremental_kriging():
    """测试增量克里金"""
    print("测试增量克里金...")

    # 创建订阅
    subscription = Subscription(
        subscription_id="test_sub",
        data_type="test",
        spatial_extent=BoundingBox(0, 100, 0, 100),
        update_frequency=5,
        interpolation_params={
            'method': 'ordinary_kriging',
            'variogram_model': {
                'model_type': 'spherical',
                'sill': 1.0,
                'range': 20.0,
                'nugget': 0.1
            },
            'grid_resolution': 10
        },
        notification_config={}
    )

    # 创建增量克里金插值器
    kriging = IncrementalKriging(subscription)

    # 添加初始数据点
    initial_points = []
    for i in range(20):
        point = DataPoint(
            x=np.random.uniform(0, 100),
            y=np.random.uniform(0, 100),
            value=np.random.randn(),
            id=f"initial_{i}"
        )
        initial_points.append(point)

    kriging.add_initial_points(initial_points)
    print(f"添加了 {len(initial_points)} 个初始数据点")

    # 增量更新
    for i in range(5):
        new_point = DataPoint(
            x=np.random.uniform(0, 100),
            y=np.random.uniform(0, 100),
            value=np.random.randn(),
            id=f"new_{i}"
        )
        result = kriging.incremental_update(new_point)
        print(f"更新 {i+1}: 版本={result.version}, "
              f"更新时间={result.statistics['update_time_ms']:.2f}ms")

    print("增量克里金测试通过！")


if __name__ == "__main__":
    test_incremental_kriging()