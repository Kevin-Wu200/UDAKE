"""
改进的采样推荐器
推荐最优采样点，支持多种策略
"""
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
import heapq

from .采样点影响评估器 import SamplingPointImpactEvaluator

logger = logging.getLogger(__name__)


class ImprovedSamplingRecommender:
    """改进的采样推荐器"""

    def __init__(
        self,
        impact_evaluator: SamplingPointImpactEvaluator = None,
        max_workers: int = 4
    ):
        """
        初始化推荐器

        参数:
        - impact_evaluator: 影响评估器实例
        - max_workers: 最大并行工作线程数
        """
        self.impact_evaluator = impact_evaluator or SamplingPointImpactEvaluator()
        self.max_workers = max_workers

    def recommend_optimal_points(
        self,
        existing_points: np.ndarray,  # shape: (n, 2) - [x, y]
        existing_values: np.ndarray,  # shape: (n,)
        variance_grid: np.ndarray = None,  # shape: (h, w) - 方差栅格
        x_coords: np.ndarray = None,  # shape: (w,) - X坐标
        y_coords: np.ndarray = None,  # shape: (h,) - Y坐标
        n_recommendations: int = 20,
        strategy: str = "impact_optimized",
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        推荐最优采样点

        参数:
        - existing_points: 现有采样点坐标
        - existing_values: 现有采样点值
        - variance_grid: 方差栅格（可选）
        - x_coords: X坐标数组
        - y_coords: Y坐标数组
        - n_recommendations: 推荐点数量
        - strategy: 推荐策略
          * impact_optimized: 基于影响优化（推荐）
          * variance_based: 基于方差优先
          * spatial_coverage: 基于空间覆盖
          * hybrid: 混合策略
        - constraints: 约束条件
          * min_distance: 最小间距
          * region_bounds: 区域边界 [min_x, min_y, max_x, max_y]
          * max_points_per_region: 每个区域最大点数

        返回:
        - 推荐结果
        """
        logger.info(f"开始推荐采样点，策略: {strategy}, 数量: {n_recommendations}")

        # 解析约束条件
        if constraints is None:
            constraints = {}

        min_distance = constraints.get('min_distance', None)
        region_bounds = constraints.get('region_bounds', None)

        # 根据策略生成推荐
        if strategy == "impact_optimized":
            recommendations = self._recommend_by_impact(
                existing_points, existing_values,
                variance_grid, x_coords, y_coords,
                n_recommendations, min_distance, region_bounds
            )
        elif strategy == "variance_based":
            recommendations = self._recommend_by_variance(
                variance_grid, x_coords, y_coords,
                existing_points, n_recommendations,
                min_distance, region_bounds
            )
        elif strategy == "spatial_coverage":
            recommendations = self._recommend_by_coverage(
                variance_grid, x_coords, y_coords,
                existing_points, n_recommendations,
                min_distance, region_bounds
            )
        elif strategy == "hybrid":
            recommendations = self._recommend_hybrid(
                existing_points, existing_values,
                variance_grid, x_coords, y_coords,
                n_recommendations, min_distance, region_bounds
            )
        else:
            logger.warning(f"未知策略: {strategy}，使用默认策略 impact_optimized")
            recommendations = self._recommend_by_impact(
                existing_points, existing_values,
                variance_grid, x_coords, y_coords,
                n_recommendations, min_distance, region_bounds
            )

        # 添加约束检查结果
        recommendations = self._apply_constraints(
            recommendations, constraints
        )

        logger.info(f"推荐完成，共推荐 {len(recommendations)} 个点")

        return {
            "strategy": strategy,
            "n_recommendations": len(recommendations),
            "recommendations": recommendations,
            "constraints_applied": constraints
        }

    def _recommend_by_impact(
        self,
        existing_points: np.ndarray,
        existing_values: np.ndarray,
        variance_grid: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        n: int,
        min_distance: float,
        region_bounds: List[float]
    ) -> List[Dict[str, Any]]:
        """
        基于影响优化推荐采样点
        """
        logger.info("使用 impact_optimized 策略推荐采样点")

        # 生成候选点
        candidates = self._generate_candidates(
            variance_grid, x_coords, y_coords,
            region_bounds, n_candidates=n * 5
        )

        if len(candidates) == 0:
            logger.warning("没有生成候选点")
            return []

        # 提取候选点坐标
        candidate_points = np.array([[c['x'], c['y']] for c in candidates])

        # 评估候选点的影响
        impact_results = self.impact_evaluator.evaluate_impact(
            existing_points, existing_values,
            candidate_points,
            grid_resolution=50
        )

        # 合并候选点信息和影响结果
        for i, (candidate, impact) in enumerate(zip(candidates, impact_results)):
            candidate.update(impact)
            candidate['id'] = i + 1

        # 按综合评分排序
        ranked_candidates = sorted(
            candidates,
            key=lambda x: x.get('comprehensive_score', 0),
            reverse=True
        )

        # 选择多样化的推荐点
        recommendations = self._select_diverse_points(
            ranked_candidates, n, min_distance
        )

        return recommendations

    def _recommend_by_variance(
        self,
        variance_grid: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        existing_points: np.ndarray,
        n: int,
        min_distance: float,
        region_bounds: List[float]
    ) -> List[Dict[str, Any]]:
        """
        基于方差优先推荐采样点
        """
        logger.info("使用 variance_based 策略推荐采样点")

        if variance_grid is None:
            logger.warning("方差栅格为空，无法使用 variance_based 策略")
            return []

        # 生成候选点（集中在高方差区域）
        candidates = self._generate_candidates(
            variance_grid, x_coords, y_coords,
            region_bounds,
            n_candidates=n * 3,
            focus_on_high_variance=True
        )

        if len(candidates) == 0:
            return []

        # 按方差排序
        ranked_candidates = sorted(
            candidates,
            key=lambda x: x.get('variance', 0),
            reverse=True
        )

        # 选择多样化的推荐点
        recommendations = self._select_diverse_points(
            ranked_candidates, n, min_distance
        )

        # 添加默认评分
        for i, rec in enumerate(recommendations):
            rec['id'] = i + 1
            rec['comprehensive_score'] = rec.get('variance', 0) / np.max(variance_grid) if np.max(variance_grid) > 0 else 0
            rec['variance_reduction'] = 0.0
            rec['variance_reduction_ratio'] = 0.0
            rec['local_improvement'] = 0.0
            rec['influence_radius'] = 0.0

        return recommendations

    def _recommend_by_coverage(
        self,
        variance_grid: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        existing_points: np.ndarray,
        n: int,
        min_distance: float,
        region_bounds: List[float]
    ) -> List[Dict[str, Any]]:
        """
        基于空间覆盖推荐采样点
        """
        logger.info("使用 spatial_coverage 策略推荐采样点")

        # 使用聚类生成均匀分布的候选点
        candidates = self._generate_candidates_by_clustering(
            variance_grid, x_coords, y_coords,
            region_bounds, n_clusters=n * 2
        )

        if len(candidates) == 0:
            return []

        # 按与现有点的距离排序（优先选择远距离点）
        if len(existing_points) > 0:
            for candidate in candidates:
                distances = cdist(
                    [[candidate['x'], candidate['y']]],
                    existing_points
                )
                candidate['min_distance_to_existing'] = float(np.min(distances))
        else:
            for candidate in candidates:
                candidate['min_distance_to_existing'] = float('inf')

        # 按距离排序
        ranked_candidates = sorted(
            candidates,
            key=lambda x: x.get('min_distance_to_existing', 0),
            reverse=True
        )

        # 选择多样化的推荐点
        recommendations = self._select_diverse_points(
            ranked_candidates, n, min_distance
        )

        # 添加默认评分
        for i, rec in enumerate(recommendations):
            rec['id'] = i + 1
            rec['comprehensive_score'] = rec.get('min_distance_to_existing', 0) / 100.0  # 归一化
            rec['variance_reduction'] = 0.0
            rec['variance_reduction_ratio'] = 0.0
            rec['local_improvement'] = 0.0
            rec['influence_radius'] = 0.0
            rec['variance'] = rec.get('variance', 0)

        return recommendations

    def _recommend_hybrid(
        self,
        existing_points: np.ndarray,
        existing_values: np.ndarray,
        variance_grid: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        n: int,
        min_distance: float,
        region_bounds: List[float]
    ) -> List[Dict[str, Any]]:
        """
        混合策略推荐采样点
        """
        logger.info("使用 hybrid 策略推荐采样点")

        # 60% 基于影响，40% 基于覆盖
        n_impact = int(n * 0.6)
        n_coverage = n - n_impact

        # 获取基于影响的推荐
        impact_recs = self._recommend_by_impact(
            existing_points, existing_values,
            variance_grid, x_coords, y_coords,
            n_impact, min_distance, region_bounds
        )

        # 获取基于覆盖的推荐
        coverage_recs = self._recommend_by_coverage(
            variance_grid, x_coords, y_coords,
            existing_points, n_coverage, min_distance, region_bounds
        )

        # 合并推荐
        all_recommendations = impact_recs + coverage_recs

        # 重新分配ID
        for i, rec in enumerate(all_recommendations):
            rec['id'] = i + 1

        return all_recommendations

    def _generate_candidates(
        self,
        variance_grid: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        region_bounds: List[float],
        n_candidates: int = 100,
        focus_on_high_variance: bool = False
    ) -> List[Dict[str, Any]]:
        """
        生成候选采样点
        """
        candidates = []

        if variance_grid is None or x_coords is None or y_coords is None:
            logger.warning("方差栅格或坐标为空，无法生成候选点")
            return candidates

        # 应用区域边界约束
        if region_bounds:
            min_x, min_y, max_x, max_y = region_bounds
            x_mask = (x_coords >= min_x) & (x_coords <= max_x)
            y_mask = (y_coords >= min_y) & (y_coords <= max_y)
            x_coords = x_coords[x_mask]
            y_coords = y_coords[y_mask]
            variance_grid = variance_grid[y_mask][:, x_mask]

        # 展平栅格
        variance_flat = variance_grid.flatten()
        xx, yy = np.meshgrid(x_coords, y_coords)
        x_flat = xx.flatten()
        y_flat = yy.flatten()

        if focus_on_high_variance:
            # 重点关注高方差区域
            threshold = np.percentile(variance_flat, 75)
            high_variance_mask = variance_flat >= threshold
            indices = np.where(high_variance_mask)[0]
        else:
            # 从整个区域采样
            indices = np.random.choice(
                len(variance_flat),
                size=min(n_candidates, len(variance_flat)),
                replace=False
            )

        for idx in indices:
            candidates.append({
                'x': float(x_flat[idx]),
                'y': float(y_flat[idx]),
                'variance': float(variance_flat[idx])
            })

        logger.info(f"生成了 {len(candidates)} 个候选点")
        return candidates

    def _generate_candidates_by_clustering(
        self,
        variance_grid: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        region_bounds: List[float],
        n_clusters: int = 20
    ) -> List[Dict[str, Any]]:
        """
        通过聚类生成候选采样点
        """
        candidates = []

        if variance_grid is None or x_coords is None or y_coords is None:
            return candidates

        # 应用区域边界约束
        if region_bounds:
            min_x, min_y, max_x, max_y = region_bounds
            x_mask = (x_coords >= min_x) & (x_coords <= max_x)
            y_mask = (y_coords >= min_y) & (y_coords <= max_y)
            x_coords = x_coords[x_mask]
            y_coords = y_coords[y_mask]
            variance_grid = variance_grid[y_mask][:, x_mask]

        # 创建网格点
        xx, yy = np.meshgrid(x_coords, y_coords)
        points = np.column_stack([xx.flatten(), yy.flatten()])
        variance_flat = variance_grid.flatten()

        # 加权采样（方差越高，被选中的概率越大）
        if np.sum(variance_flat) > 0:
            probabilities = variance_flat / np.sum(variance_flat)
        else:
            probabilities = np.ones(len(variance_flat)) / len(variance_flat)

        # 采样用于聚类的点
        n_samples = min(len(points), n_clusters * 10)
        sampled_indices = np.random.choice(
            len(points),
            size=n_samples,
            replace=False,
            p=probabilities
        )
        sampled_points = points[sampled_indices]

        # 执行聚类
        if len(sampled_points) >= n_clusters:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(sampled_points)
            cluster_centers = kmeans.cluster_centers_

            # 找到每个簇中方差最大的点
            for i in range(n_clusters):
                cluster_mask = cluster_labels == i
                cluster_indices = sampled_indices[cluster_mask]
                cluster_variances = variance_flat[cluster_indices]

                if len(cluster_variances) > 0:
                    best_idx_in_cluster = cluster_indices[np.argmax(cluster_variances)]
                    best_point = points[best_idx_in_cluster]

                    candidates.append({
                        'x': float(best_point[0]),
                        'y': float(best_point[1]),
                        'variance': float(variance_flat[best_idx_in_cluster])
                    })
        else:
            # 如果点数太少，直接使用采样点
            for idx in sampled_indices:
                candidates.append({
                    'x': float(points[idx, 0]),
                    'y': float(points[idx, 1]),
                    'variance': float(variance_flat[idx])
                })

        logger.info(f"通过聚类生成了 {len(candidates)} 个候选点")
        return candidates

    def _select_diverse_points(
        self,
        ranked_candidates: List[Dict[str, Any]],
        n: int,
        min_distance: float
    ) -> List[Dict[str, Any]]:
        """
        选择多样化的推荐点
        """
        if len(ranked_candidates) == 0:
            return []

        selected = []
        remaining = ranked_candidates.copy()

        # 添加第一个点（评分最高的）
        selected.append(remaining.pop(0))

        # 贪心算法选择剩余点
        while len(selected) < n and len(remaining) > 0:
            best_candidate = None
            best_score = -float('inf')

            for candidate in remaining:
                # 计算与已选点的最小距离
                candidate_pos = np.array([candidate['x'], candidate['y']])
                selected_positions = np.array([[s['x'], s['y']] for s in selected])

                if len(selected_positions) > 0:
                    distances = cdist([candidate_pos], selected_positions)
                    min_dist = np.min(distances)
                else:
                    min_dist = float('inf')

                # 检查最小距离约束
                if min_distance is not None and min_dist < min_distance:
                    continue

                # 计算综合得分（评分 + 多样性）
                diversity_score = min_dist
                impact_score = candidate.get('comprehensive_score', 0)

                # 加权综合得分
                combined_score = 0.7 * impact_score + 0.3 * (diversity_score / 100.0)

                if combined_score > best_score:
                    best_score = combined_score
                    best_candidate = candidate

            if best_candidate:
                selected.append(best_candidate)
                remaining.remove(best_candidate)
            else:
                # 如果没有满足约束的候选点，选择评分最高的
                if remaining:
                    selected.append(remaining.pop(0))

        return selected

    def _apply_constraints(
        self,
        recommendations: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        应用约束条件
        """
        if not constraints:
            return recommendations

        max_points_per_region = constraints.get('max_points_per_region', None)

        if max_points_per_region is not None:
            # 简单实现：限制推荐数量
            recommendations = recommendations[:max_points_per_region]

        return recommendations

    def rank_by_comprehensive_score(
        self,
        candidates: List[Dict[str, Any]],
        weights: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """
        按综合评分排序候选点

        参数:
        - candidates: 候选点列表
        - weights: 权重配置
          * variance_reduction: 方差减少权重
          * local_improvement: 局部改善权重
          * spatial_diversity: 空间多样性权重

        返回:
        - 排序后的候选点列表
        """
        if weights is None:
            weights = {
                'variance_reduction': 0.5,
                'local_improvement': 0.3,
                'spatial_diversity': 0.2
            }

        # 计算每个候选点的综合评分
        for i, candidate in enumerate(candidates):
            variance_reduction = candidate.get('variance_reduction_ratio', 0)
            local_improvement = candidate.get('local_improvement', 0)

            # 计算空间多样性（与已选点的平均距离）
            if i > 0:
                selected_positions = np.array([[c['x'], c['y']] for c in candidates[:i]])
                candidate_pos = np.array([candidate['x'], candidate['y']])
                distances = cdist([candidate_pos], selected_positions)
                spatial_diversity = float(np.mean(distances))
                # 归一化到 [0, 1]
                spatial_diversity = min(spatial_diversity / 100.0, 1.0)
            else:
                spatial_diversity = 1.0

            # 计算综合评分
            comprehensive_score = (
                weights['variance_reduction'] * variance_reduction +
                weights['local_improvement'] * local_improvement +
                weights['spatial_diversity'] * spatial_diversity
            )

            candidate['comprehensive_score'] = comprehensive_score

        # 按综合评分排序
        sorted_candidates = sorted(
            candidates,
            key=lambda x: x.get('comprehensive_score', 0),
            reverse=True
        )

        return sorted_candidates
