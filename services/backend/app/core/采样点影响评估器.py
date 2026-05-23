"""
采样点影响评估器
通过LOO交叉验证评估候选采样点对插值精度的影响
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import numpy as np
from pykrige.ok import OrdinaryKriging
from sklearn.metrics import mean_squared_error

logger = logging.getLogger(__name__)


class SamplingPointImpactEvaluator:
    """采样点影响评估器"""

    def __init__(
        self,
        variogram_model: str = "spherical",
        nlags: int = 6,
        max_workers: int = 4
    ):
        """
        初始化评估器

        参数:
        - variogram_model: 变异函数模型
        - nlags: 滞后数
        - max_workers: 最大并行工作线程数
        """
        self.variogram_model = variogram_model
        self.nlags = nlags
        self.max_workers = max_workers

    def evaluate_impact(
        self,
        existing_points: np.ndarray,  # shape: (n, 2) - [x, y]
        existing_values: np.ndarray,  # shape: (n,)
        candidate_points: np.ndarray,  # shape: (m, 2) - [x, y]
        candidate_values: np.ndarray = None,  # shape: (m,) - 如果为None，需要估算
        grid_resolution: int = 50,
        influence_radius: float = None
    ) -> List[Dict[str, Any]]:
        """
        评估候选采样点的影响

        参数:
        - existing_points: 现有采样点坐标
        - existing_values: 现有采样点值
        - candidate_points: 候选采样点坐标
        - candidate_values: 候选采样点值（如果为None，将通过克里金估算）
        - grid_resolution: 评估网格分辨率
        - influence_radius: 影响半径（如果为None，自动计算）

        返回:
        - 评估结果列表，每个候选点包含：
          * variance_reduction: 方差减少量
          * local_improvement: 局部改善度
          * comprehensive_score: 综合评分
          * influence_radius: 影响半径
        """
        logger.info(f"开始评估 {len(candidate_points)} 个候选点的影响")

        # 计算当前基线性能
        baseline_variance = self._calculate_baseline_variance(
            existing_points, existing_values, grid_resolution
        )
        logger.info(f"基线方差: {baseline_variance:.6f}")

        # 如果没有提供候选值，使用克里金估算
        if candidate_values is None:
            candidate_values = self._estimate_candidate_values(
                existing_points, existing_values, candidate_points
            )

        # 自动计算影响半径（如果没有提供）
        if influence_radius is None:
            influence_radius = self._calculate_influence_radius(
                existing_points, candidate_points
            )
        logger.info(f"影响半径: {influence_radius:.2f}")

        # 并行评估每个候选点
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._evaluate_single_candidate,
                    existing_points,
                    existing_values,
                    candidate_points[i],
                    candidate_values[i],
                    baseline_variance,
                    grid_resolution,
                    influence_radius
                ): i for i in range(len(candidate_points))
            }

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    result["candidate_index"] = idx
                    results.append(result)
                except Exception as e:
                    logger.error(f"评估候选点 {idx} 失败: {str(e)}")
                    results.append({
                        "candidate_index": idx,
                        "error": str(e),
                        "variance_reduction": 0.0,
                        "local_improvement": 0.0,
                        "comprehensive_score": 0.0,
                        "influence_radius": influence_radius
                    })

        logger.info(f"评估完成，成功评估 {len([r for r in results if 'error' not in r])} 个候选点")

        return results

    def _evaluate_single_candidate(
        self,
        existing_points: np.ndarray,
        existing_values: np.ndarray,
        candidate_point: np.ndarray,
        candidate_value: float,
        baseline_variance: float,
        grid_resolution: int,
        influence_radius: float
    ) -> Dict[str, Any]:
        """
        评估单个候选点的影响
        """
        # 添加候选点到现有数据
        combined_points = np.vstack([existing_points, candidate_point])
        combined_values = np.append(existing_values, candidate_value)

        # 计算添加候选点后的方差
        new_variance = self._calculate_variance_with_candidate(
            combined_points, combined_values, grid_resolution
        )

        # 计算方差减少量
        variance_reduction = baseline_variance - new_variance
        variance_reduction_ratio = variance_reduction / baseline_variance if baseline_variance > 0 else 0

        # 计算局部改善度
        local_improvement = self._calculate_local_improvement(
            existing_points, existing_values,
            candidate_point, candidate_value,
            influence_radius
        )

        # 计算综合评分
        comprehensive_score = self._calculate_comprehensive_score(
            variance_reduction_ratio,
            local_improvement
        )

        return {
            "variance_reduction": float(variance_reduction),
            "variance_reduction_ratio": float(variance_reduction_ratio),
            "local_improvement": float(local_improvement),
            "comprehensive_score": float(comprehensive_score),
            "influence_radius": float(influence_radius)
        }

    def _calculate_baseline_variance(
        self,
        points: np.ndarray,
        values: np.ndarray,
        grid_resolution: int
    ) -> float:
        """
        计算基线方差
        """
        try:
            # 创建克里金模型
            ok = OrdinaryKriging(
                points[:, 0], points[:, 1], values,
                variogram_model=self.variogram_model,
                nlags=self.nlags,
                enable_plotting=False
            )

            # 生成评估网格
            grid_x = np.linspace(points[:, 0].min(), points[:, 0].max(), grid_resolution)
            grid_y = np.linspace(points[:, 1].min(), points[:, 1].max(), grid_resolution)

            # 执行插值
            _, variance = ok.execute('grid', grid_x, grid_y)

            # 返回平均方差
            return float(np.mean(variance))

        except Exception as e:
            logger.error(f"计算基线方差失败: {str(e)}")
            return 0.0

    def _calculate_variance_with_candidate(
        self,
        points: np.ndarray,
        values: np.ndarray,
        grid_resolution: int
    ) -> float:
        """
        计算添加候选点后的方差
        """
        try:
            # 创建克里金模型
            ok = OrdinaryKriging(
                points[:, 0], points[:, 1], values,
                variogram_model=self.variogram_model,
                nlags=self.nlags,
                enable_plotting=False
            )

            # 生成评估网格
            grid_x = np.linspace(points[:, 0].min(), points[:, 0].max(), grid_resolution)
            grid_y = np.linspace(points[:, 1].min(), points[:, 1].max(), grid_resolution)

            # 执行插值
            _, variance = ok.execute('grid', grid_x, grid_y)

            # 返回平均方差
            return float(np.mean(variance))

        except Exception as e:
            logger.error(f"计算候选点方差失败: {str(e)}")
            return 0.0

    def _estimate_candidate_values(
        self,
        existing_points: np.ndarray,
        existing_values: np.ndarray,
        candidate_points: np.ndarray
    ) -> np.ndarray:
        """
        估算候选点的值
        """
        try:
            # 创建克里金模型
            ok = OrdinaryKriging(
                existing_points[:, 0], existing_points[:, 1], existing_values,
                variogram_model=self.variogram_model,
                nlags=self.nlags,
                enable_plotting=False
            )

            # 预测候选点值
            predicted, _ = ok.execute('points', candidate_points[:, 0], candidate_points[:, 1])

            return predicted

        except Exception as e:
            logger.error(f"估算候选点值失败: {str(e)}")
            # 返回平均值作为回退
            return np.full(len(candidate_points), np.mean(existing_values))

    def _calculate_local_improvement(
        self,
        existing_points: np.ndarray,
        existing_values: np.ndarray,
        candidate_point: np.ndarray,
        candidate_value: float,
        influence_radius: float
    ) -> float:
        """
        计算局部改善度
        """
        # 计算候选点到所有现有点的距离
        distances = np.sqrt(np.sum((existing_points - candidate_point) ** 2, axis=1))

        # 找到影响半径内的点
        in_radius_mask = distances <= influence_radius
        if np.sum(in_radius_mask) == 0:
            return 0.0

        # 获取影响半径内的点
        local_points = existing_points[in_radius_mask]  # noqa: F841
        local_values = existing_values[in_radius_mask]

        # 计算局部方差
        local_variance = np.var(local_values)
        if local_variance == 0:
            return 0.0

        # 计算添加候选点后的局部方差
        combined_local_values = np.append(local_values, candidate_value)
        new_local_variance = np.var(combined_local_values)

        # 计算局部改善度
        local_improvement = (local_variance - new_local_variance) / local_variance

        return float(local_improvement)

    def _calculate_comprehensive_score(
        self,
        variance_reduction_ratio: float,
        local_improvement: float
    ) -> float:
        """
        计算综合评分

        参数:
        - variance_reduction_ratio: 方差减少比例 (0-1)
        - local_improvement: 局部改善度 (0-1)

        返回:
        - 综合评分 (0-1)
        """
        # 加权综合评分：70% 方差减少 + 30% 局部改善
        weight_variance = 0.7
        weight_local = 0.3

        comprehensive_score = (
            weight_variance * variance_reduction_ratio +
            weight_local * local_improvement
        )

        return float(comprehensive_score)

    def _calculate_influence_radius(
        self,
        existing_points: np.ndarray,
        candidate_points: np.ndarray
    ) -> float:
        """
        自动计算影响半径
        """
        # 计算现有点之间的平均距离
        n = len(existing_points)
        if n < 2:
            # 如果只有1个点，使用候选点的范围作为参考
            if len(candidate_points) > 1:
                distances = np.sqrt(
                    np.sum((candidate_points[1:] - candidate_points[:-1]) ** 2, axis=1)
                )
                return float(np.mean(distances)) if len(distances) > 0 else 1.0
            return 1.0

        # 计算所有现有点之间的距离
        from scipy.spatial.distance import pdist
        distances = pdist(existing_points)
        mean_distance = np.mean(distances)

        # 影响半径为平均距离的1.5倍
        influence_radius = mean_distance * 1.5

        return float(influence_radius)

    def perform_loo_validation(
        self,
        points: np.ndarray,
        values: np.ndarray
    ) -> Dict[str, float]:
        """
        执行留一法（LOO）交叉验证

        参数:
        - points: 采样点坐标
        - values: 采样点值

        返回:
        - 验证指标
        """
        n = len(points)
        predictions = []
        actuals = []

        logger.info(f"开始LOO交叉验证，共 {n} 个点")

        for i in range(n):
            # 移除第i个点
            train_points = np.delete(points, i, axis=0)
            train_values = np.delete(values, i)

            # 预测第i个点
            try:
                ok = OrdinaryKriging(
                    train_points[:, 0], train_points[:, 1], train_values,
                    variogram_model=self.variogram_model,
                    nlags=self.nlags,
                    enable_plotting=False
                )

                pred, _ = ok.execute('points', [points[i, 0]], [points[i, 1]])
                predictions.append(pred[0])
                actuals.append(values[i])

            except Exception as e:
                logger.warning(f"LOO验证第 {i} 个点失败: {str(e)}")
                continue

        if len(predictions) == 0:
            return {
                "rmse": 0.0,
                "mae": 0.0,
                "r2": 0.0,
                "n_valid": 0
            }

        predictions = np.array(predictions)
        actuals = np.array(actuals)

        # 计算指标
        mse = mean_squared_error(actuals, predictions)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(actuals - predictions))

        # 计算R²
        ss_res = np.sum((actuals - predictions) ** 2)
        ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "rmse": float(rmse),
            "mae": float(mae),
            "r2": float(r2),
            "n_valid": len(predictions)
        }
