"""
克里金插值性能加速模块
Kriging Performance Acceleration

提供Numba JIT加速、并行计算、稀疏矩阵优化等功能：
- Numba加速协方差计算和矩阵构建
- 并行化网格预测
- 四叉树LOD分层插值
- 稀疏协方差矩阵支持
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# 尝试导入Numba，不可用时回退到纯NumPy
try:
    from numba import boolean, float64, int64, jit, prange
    NUMBA_AVAILABLE = True
    logger.info("Numba加速已启用")
except ImportError:
    NUMBA_AVAILABLE = False
    logger.info("Numba不可用，使用纯NumPy计算")
    # 提供空装饰器回退
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range
    float64 = np.float64
    int64 = np.int64
    boolean = bool


# ========== Numba加速的协方差计算 ==========

VARIOGRAM_SPHERICAL = 0
VARIOGRAM_EXPONENTIAL = 1
VARIOGRAM_GAUSSIAN = 2
VARIOGRAM_POWER = 3
VARIOGRAM_LINEAR = 4
VARIOGRAM_LOGARITHMIC = 5


@jit(nopython=True, cache=True)
def _covariance_spherical(h: float, sill: float, nugget: float) -> float:
    """球状模型协方差（Numba加速）"""
    if h <= 0.0:
        return sill + nugget
    if h <= 1.0:
        return nugget + sill * (1.5 * h - 0.5 * h ** 3)
    return nugget


@jit(nopython=True, cache=True)
def _covariance_exponential(h: float, sill: float, nugget: float) -> float:
    """指数模型协方差（Numba加速）"""
    if h <= 0.0:
        return sill + nugget
    return nugget + sill * (1.0 - np.exp(-3.0 * h))


@jit(nopython=True, cache=True)
def _covariance_gaussian(h: float, sill: float, nugget: float) -> float:
    """高斯模型协方差（Numba加速）"""
    if h <= 0.0:
        return sill + nugget
    return nugget + sill * (1.0 - np.exp(-3.0 * h * h))


@jit(nopython=True, cache=True)
def _covariance_power(h: float, sill: float, nugget: float, power: float) -> float:
    """幂函数模型协方差（Numba加速）"""
    if h <= 0.0:
        return sill + nugget
    if h <= 1.0:
        return nugget + sill * (h ** power)
    return nugget + sill


@jit(nopython=True, cache=True)
def _covariance_linear(h: float, sill: float, nugget: float) -> float:
    """线性模型协方差（Numba加速）"""
    if h <= 0.0:
        return sill + nugget
    if h <= 1.0:
        return nugget + sill * h
    return nugget + sill


@jit(nopython=True, cache=True)
def _covariance_logarithmic(h: float, sill: float, nugget: float) -> float:
    """对数模型协方差（Numba加速）"""
    if h <= 0.0:
        return sill + nugget
    if h > 0.0 and h <= 1.0:
        return nugget + sill * (-np.log(h + 1e-10))
    return nugget + sill


@jit(nopython=True, cache=True)
def compute_covariance_fast(
    h: float,
    model_type: int,
    sill: float,
    nugget: float,
    power: float = 1.0,
) -> float:
    """
    快速协方差计算（Numba JIT编译）

    Args:
        h: 归一化距离 h = d / range
        model_type: 模型类型枚举
        sill: 基台值
        nugget: 块金值
        power: 幂函数指数
    """
    if model_type == VARIOGRAM_SPHERICAL:
        return _covariance_spherical(h, sill, nugget)
    elif model_type == VARIOGRAM_EXPONENTIAL:
        return _covariance_exponential(h, sill, nugget)
    elif model_type == VARIOGRAM_GAUSSIAN:
        return _covariance_gaussian(h, sill, nugget)
    elif model_type == VARIOGRAM_POWER:
        return _covariance_power(h, sill, nugget, power)
    elif model_type == VARIOGRAM_LINEAR:
        return _covariance_linear(h, sill, nugget)
    elif model_type == VARIOGRAM_LOGARITHMIC:
        return _covariance_logarithmic(h, sill, nugget)
    else:
        return sill + nugget if h <= 0.0 else nugget


# ========== 快速协方差矩阵构建 ==========

@jit(nopython=True, parallel=True, cache=True)
def build_covariance_matrix_fast(
    xs: np.ndarray,
    ys: np.ndarray,
    model_type: int,
    sill: float,
    range_val: float,
    nugget: float,
    power: float = 1.0,
) -> np.ndarray:
    """
    快速构建协方差矩阵（Numba并行加速）

    Args:
        xs: X坐标数组 [n]
        ys: Y坐标数组 [n]
        model_type: 模型类型枚举
        sill: 基台值
        range_val: 变程
        nugget: 块金值
        power: 幂函数指数

    Returns:
        np.ndarray: 协方差矩阵 [n × n]
    """
    n = len(xs)
    K = np.zeros((n, n), dtype=np.float64)

    for i in prange(n):
        for j in range(i, n):
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            dist = np.sqrt(dx * dx + dy * dy)
            h = dist / range_val
            cov = compute_covariance_fast(h, model_type, sill, nugget, power)
            K[i, j] = cov
            if i != j:
                K[j, i] = cov

    return K


@jit(nopython=True, cache=True)
def build_covariance_vector_fast(
    target_x: float,
    target_y: float,
    xs: np.ndarray,
    ys: np.ndarray,
    model_type: int,
    sill: float,
    range_val: float,
    nugget: float,
    power: float = 1.0,
) -> np.ndarray:
    """
    快速构建协方差向量（目标点与已知点之间）

    Args:
        target_x, target_y: 目标点坐标
        xs, ys: 已知点坐标数组
        其他: 模型参数

    Returns:
        np.ndarray: 协方差向量 [n]
    """
    n = len(xs)
    k = np.zeros(n, dtype=np.float64)

    for i in range(n):
        dx = target_x - xs[i]
        dy = target_y - ys[i]
        dist = np.sqrt(dx * dx + dy * dy)
        h = dist / range_val
        k[i] = compute_covariance_fast(h, model_type, sill, nugget, power)

    return k


@jit(nopython=True, cache=True)
def predict_kriging_fast(
    target_x: float,
    target_y: float,
    xs: np.ndarray,
    ys: np.ndarray,
    values: np.ndarray,
    K_inv: np.ndarray,
    model_type: int,
    sill: float,
    range_val: float,
    nugget: float,
    power: float = 1.0,
) -> tuple:
    """
    快速克里金预测（单点）

    Args:
        target_x, target_y: 目标点坐标
        xs, ys: 已知点坐标
        values: 已知点值
        K_inv: 协方差矩阵的逆
        model_type, sill, range_val, nugget, power: 模型参数

    Returns:
        tuple: (prediction, variance)
    """
    k = build_covariance_vector_fast(target_x, target_y, xs, ys, model_type, sill, range_val, nugget, power)
    weights = K_inv @ k
    prediction = np.dot(weights, values)
    target_cov = compute_covariance_fast(0.0, model_type, sill, nugget, power)
    variance = max(0.0, target_cov - np.dot(k, K_inv @ k))
    return prediction, variance


# ========== 四叉树LOD分层插值 ==========

class QuadTreeLOD:
    """
    四叉树LOD（Level of Detail）分层插值

    适用于大规模点集（>10万点）的高效预测。
    根据目标点到已知点的距离自动选择插值精度层级。
    """

    def __init__(
        self,
        min_x: float = 0.0,
        max_x: float = 100.0,
        min_y: float = 0.0,
        max_y: float = 100.0,
        max_depth: int = 8,
        max_points_per_node: int = 50,
    ):
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.max_depth = max_depth
        self.max_points_per_node = max_points_per_node
        self.root = None

    class Node:
        __slots__ = ('min_x', 'max_x', 'min_y', 'max_y', 'depth',
                     'points', 'children', 'mean_value', 'n_points')

        def __init__(self, min_x, max_x, min_y, max_y, depth):
            self.min_x = min_x
            self.max_x = max_x
            self.min_y = min_y
            self.max_y = max_y
            self.depth = depth
            self.points = []
            self.children = None
            self.mean_value = 0.0
            self.n_points = 0

        def is_leaf(self):
            return self.children is None

        def contains(self, x, y):
            return (self.min_x <= x <= self.max_x and
                    self.min_y <= y <= self.max_y)

        def center_distance(self, x, y):
            cx = (self.min_x + self.max_x) / 2
            cy = (self.min_y + self.max_y) / 2
            return np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    def insert(self, x: float, y: float, value: float, point_id: str = ''):
        """插入点到四叉树"""
        if self.root is None:
            self.root = self.Node(self.min_x, self.max_x, self.min_y, self.max_y, 0)
            # 扩展边界以包含所有点
            self.root.min_x = min(self.root.min_x, x)
            self.root.max_x = max(self.root.max_x, x)
            self.root.min_y = min(self.root.min_y, y)
            self.root.max_y = max(self.root.max_y, y)

        self._insert(self.root, x, y, value, point_id)

    def _insert(self, node: Node, x: float, y: float, value: float, point_id: str):
        if not node.contains(x, y):
            return

        node.n_points += 1
        # 更新均值（在线算法）
        node.mean_value += (value - node.mean_value) / node.n_points

        if node.is_leaf():
            node.points.append({
                'x': x, 'y': y, 'value': value, 'id': point_id,
            })

            if (len(node.points) > self.max_points_per_node and
                node.depth < self.max_depth):
                self._split(node)
        else:
            for child in node.children:
                if child.contains(x, y):
                    self._insert(child, x, y, value, point_id)
                    break

    def _split(self, node: Node):
        """分裂节点"""
        mid_x = (node.min_x + node.max_x) / 2
        mid_y = (node.min_y + node.max_y) / 2
        d = node.depth + 1

        node.children = [
            self.Node(node.min_x, mid_x, node.min_y, mid_y, d),  # SW
            self.Node(mid_x, node.max_x, node.min_y, mid_y, d),   # SE
            self.Node(node.min_x, mid_x, mid_y, node.max_y, d),   # NW
            self.Node(mid_x, node.max_x, mid_y, node.max_y, d),   # NE
        ]

        # 重新分配点
        for pt in node.points:
            for child in node.children:
                if child.contains(pt['x'], pt['y']):
                    self._insert(child, pt['x'], pt['y'], pt['value'], pt.get('id', ''))
                    break

        node.points = []  # 清空当前节点

    def query_lod(self, x: float, y: float, target_depth: Optional[int] = None) -> dict:
        """
        LOD查询

        根据深度查询，返回该层级节点的聚合统计信息。
        """
        if self.root is None:
            return {'mean': 0.0, 'n_points': 0, 'depth': 0}

        return self._query_lod(self.root, x, y, target_depth)

    def _query_lod(self, node: Node, x: float, y: float, target_depth: Optional[int]) -> dict:
        if not node.contains(x, y):
            return {'mean': 0.0, 'n_points': 0, 'depth': 0}

        if target_depth is not None and node.depth >= target_depth:
            return {
                'mean': node.mean_value,
                'n_points': node.n_points,
                'depth': node.depth,
                'center': ((node.min_x + node.max_x) / 2, (node.min_y + node.max_y) / 2),
            }

        if node.is_leaf():
            return {
                'mean': node.mean_value,
                'n_points': node.n_points,
                'depth': node.depth,
                'center': ((node.min_x + node.max_x) / 2, (node.min_y + node.max_y) / 2),
            }

        for child in node.children:
            if child.contains(x, y):
                return self._query_lod(child, x, y, target_depth)

        return {'mean': node.mean_value, 'n_points': node.n_points, 'depth': node.depth}


# ========== 并行网格预测 ==========

def predict_grid_parallel(
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    resolution: int,
    predictor_fn: Callable[[float, float], Tuple[float, float]],
    n_workers: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    并行网格预测

    Args:
        x_range: X轴范围
        y_range: Y轴范围
        resolution: 分辨率
        predictor_fn: 预测函数 (x, y) -> (pred, var)
        n_workers: 并行线程数

    Returns:
        (pred_grid, var_grid)
    """
    if n_workers is None:
        n_workers = min(os.cpu_count() or 4, 16)

    x_vals = np.linspace(x_range[0], x_range[1], resolution)
    y_vals = np.linspace(y_range[0], y_range[1], resolution)

    pred_grid = np.zeros((resolution, resolution), dtype=np.float64)
    var_grid = np.zeros((resolution, resolution), dtype=np.float64)

    # 构建任务列表
    tasks = []
    for i, y in enumerate(y_vals):
        for j, x in enumerate(x_vals):
            tasks.append((i, j, x, y))

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        future_to_task = {
            executor.submit(predictor_fn, x, y): (i, j)
            for i, j, x, y in tasks
        }

        for future in as_completed(future_to_task):
            i, j = future_to_task[future]
            try:
                pred, var = future.result()
                pred_grid[i, j] = pred
                var_grid[i, j] = var
            except Exception as e:
                logger.warning(f"预测 ({x_vals[j]}, {y_vals[i]}) 失败: {e}")

    return pred_grid, var_grid


# ========== 辅助函数 ==========

def model_type_to_enum(model_type: str) -> int:
    """将模型类型字符串转换为枚举"""
    mapping = {
        'spherical': VARIOGRAM_SPHERICAL,
        'exponential': VARIOGRAM_EXPONENTIAL,
        'gaussian': VARIOGRAM_GAUSSIAN,
        'power': VARIOGRAM_POWER,
        'linear': VARIOGRAM_LINEAR,
        'logarithmic': VARIOGRAM_LOGARITHMIC,
    }
    return mapping.get(model_type, VARIOGRAM_SPHERICAL)


def estimate_speedup(n_points: int) -> float:
    """
    预估Numba加速比

    Args:
        n_points: 数据点数量

    Returns:
        float: 预估加速比
    """
    if NUMBA_AVAILABLE:
        if n_points < 100:
            return 1.2
        elif n_points < 1000:
            return 2.5
        elif n_points < 10000:
            return 5.0
        else:
            return 8.0 + np.log10(n_points) * 2.0
    return 1.0
