"""
3D指示克里金引擎
用于概率估计和分类
"""
import numpy as np
from typing import Dict, Any, Optional, List
from .变异函数3D import Variogram3D
import logging

logger = logging.getLogger(__name__)


class IndicatorKriging3D:
    """3D指示克里金插值引擎"""

    def interpolate(
        self,
        points: np.ndarray,
        values: np.ndarray,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        grid_z: np.ndarray,
        threshold: float,
        variogram_model: str = "spherical",
        nlags: int = 12,
        n_closest: int = 16,
        anisotropy_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        执行3D指示克里金插值
        将连续值转换为指示变量（0/1），估计超过阈值的概率
        """
        # 指示变量转换
        indicators = (values >= threshold).astype(float)
        logger.info(f"指示克里金阈值: {threshold}, 超标比例: {indicators.mean():.2%}")

        # 对指示变量拟合变异函数
        lags, sv, counts = Variogram3D.compute_experimental(
            points, indicators, nlags, anisotropy_params=anisotropy_params
        )
        vario_result = Variogram3D.fit(lags, sv, variogram_model, counts)
        model_type = vario_result["model_type"]
        nugget = vario_result["nugget"]
        sill = vario_result["sill"]
        range_ = vario_result["range"]
        model_func = Variogram3D.MODELS[model_type]

        nx, ny, nz = len(grid_x), len(grid_y), len(grid_z)
        probability = np.zeros((nx, ny, nz))
        variance = np.zeros((nx, ny, nz))

        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    target = np.array([grid_x[i], grid_y[j], grid_z[k]])
                    prob, var = self._kriging_at_point(
                        target, points, indicators, nugget, sill, range_,
                        model_func, n_closest
                    )
                    probability[i, j, k] = prob
                    variance[i, j, k] = var

            if (i + 1) % max(1, nx // 10) == 0:
                logger.info(f"指示克里金进度: {(i+1)/nx*100:.1f}%")

        return {
            "probability": probability,
            "variance": variance,
            "variogram": vario_result,
            "threshold": threshold,
            "grid_x": grid_x.tolist(),
            "grid_y": grid_y.tolist(),
            "grid_z": grid_z.tolist(),
        }

    def _kriging_at_point(
        self,
        target: np.ndarray,
        points: np.ndarray,
        indicators: np.ndarray,
        nugget: float,
        sill: float,
        range_: float,
        model_func,
        n_closest: int
    ) -> tuple:
        """在单个目标点执行指示克里金估计"""
        dists = np.sqrt(np.sum((points - target) ** 2, axis=1))
        if n_closest < len(points):
            idx = np.argpartition(dists, n_closest)[:n_closest]
        else:
            idx = np.arange(len(points))

        local_points = points[idx]
        local_indicators = indicators[idx]
        n = len(idx)

        C = np.zeros((n + 1, n + 1))
        for a in range(n):
            for b in range(a + 1, n):
                d = np.sqrt(np.sum((local_points[a] - local_points[b]) ** 2))
                cov = sill - model_func(np.array([d]), nugget, sill, range_)[0]
                C[a, b] = cov
                C[b, a] = cov
            C[a, a] = sill
        C[:n, n] = 1.0
        C[n, :n] = 1.0

        c0 = np.zeros(n + 1)
        for a in range(n):
            d = np.sqrt(np.sum((local_points[a] - target) ** 2))
            c0[a] = sill - model_func(np.array([d]), nugget, sill, range_)[0]
        c0[n] = 1.0

        try:
            weights = np.linalg.solve(C, c0)
            prob = float(np.dot(weights[:n], local_indicators))
            prob = np.clip(prob, 0.0, 1.0)
            var = float(sill - np.dot(weights[:n], c0[:n]) - weights[n])
            var = max(var, 0.0)
        except np.linalg.LinAlgError:
            local_dists = dists[idx]
            w = 1.0 / (local_dists + 1e-10)
            w /= w.sum()
            prob = float(np.clip(np.dot(w, local_indicators), 0.0, 1.0))
            var = float(np.var(local_indicators))

        return prob, var

    def multi_threshold(
        self,
        points: np.ndarray,
        values: np.ndarray,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        grid_z: np.ndarray,
        thresholds: List[float],
        **kwargs
    ) -> Dict[str, Any]:
        """多阈值指示克里金，生成累积概率分布"""
        results = {}
        for threshold in sorted(thresholds):
            result = self.interpolate(
                points, values, grid_x, grid_y, grid_z, threshold, **kwargs
            )
            results[f"threshold_{threshold}"] = {
                "probability": result["probability"],
                "variance": result["variance"],
                "variogram": result["variogram"],
            }
        results["thresholds"] = thresholds
        results["grid_x"] = grid_x.tolist()
        results["grid_y"] = grid_y.tolist()
        results["grid_z"] = grid_z.tolist()
        return results
