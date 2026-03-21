"""
3D普通克里金引擎
"""
import numpy as np
from typing import Dict, Any, Optional
from .变异函数3D import Variogram3D
from .距离计算 import Distance3D
import logging

logger = logging.getLogger(__name__)


class OrdinaryKriging3D:
    """3D普通克里金插值引擎"""

    def __init__(self):
        self.variogram_params = None
        self.model_func = None

    def interpolate(
        self,
        points: np.ndarray,
        values: np.ndarray,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        grid_z: np.ndarray,
        variogram_model: str = "spherical",
        nlags: int = 12,
        n_closest: int = 16,
        anisotropy_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        执行3D普通克里金插值
        points: (n, 3) 已知点坐标
        values: (n,) 已知点值
        grid_x, grid_y, grid_z: 网格坐标一维数组
        返回: prediction和variance的3D数组
        """
        # 拟合变异函数
        vario_result = Variogram3D.auto_fit(points, values, nlags, anisotropy_params) \
            if variogram_model == "auto" else \
            Variogram3D.fit(
                *Variogram3D.compute_experimental(points, values, nlags, anisotropy_params=anisotropy_params)[:2],
                model_type=variogram_model
            )

        self.variogram_params = vario_result
        model_type = vario_result["model_type"]
        nugget = vario_result["nugget"]
        sill = vario_result["sill"]
        range_ = vario_result["range"]
        self.model_func = Variogram3D.MODELS[model_type]

        logger.info(f"变异函数: {model_type}, nugget={nugget:.4f}, sill={sill:.4f}, range={range_:.4f}")

        # 创建3D网格
        nx, ny, nz = len(grid_x), len(grid_y), len(grid_z)
        prediction = np.zeros((nx, ny, nz))
        variance = np.zeros((nx, ny, nz))

        total_cells = nx * ny * nz
        processed = 0

        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    target = np.array([grid_x[i], grid_y[j], grid_z[k]])
                    pred, var = self._kriging_at_point(
                        target, points, values, nugget, sill, range_, n_closest
                    )
                    prediction[i, j, k] = pred
                    variance[i, j, k] = var
                    processed += 1

            if (i + 1) % max(1, nx // 10) == 0:
                logger.info(f"插值进度: {processed}/{total_cells} ({100*processed/total_cells:.1f}%)")

        return {
            "prediction": prediction,
            "variance": variance,
            "variogram": vario_result,
            "grid_x": grid_x.tolist(),
            "grid_y": grid_y.tolist(),
            "grid_z": grid_z.tolist(),
        }

    def _kriging_at_point(
        self,
        target: np.ndarray,
        points: np.ndarray,
        values: np.ndarray,
        nugget: float,
        sill: float,
        range_: float,
        n_closest: int
    ) -> tuple:
        """在单个目标点执行克里金估计"""
        # 找最近的n_closest个点
        dists = np.sqrt(np.sum((points - target) ** 2, axis=1))
        if n_closest < len(points):
            idx = np.argpartition(dists, n_closest)[:n_closest]
        else:
            idx = np.arange(len(points))

        local_points = points[idx]
        local_values = values[idx]
        local_dists = dists[idx]
        n = len(idx)

        # 构建克里金方程组 (n+1) x (n+1)
        # [C  1] [w]   [c0]
        # [1  0] [mu] = [1 ]
        C = np.zeros((n + 1, n + 1))
        for a in range(n):
            for b in range(a + 1, n):
                d = np.sqrt(np.sum((local_points[a] - local_points[b]) ** 2))
                cov = sill - self.model_func(np.array([d]), nugget, sill, range_)[0]
                C[a, b] = cov
                C[b, a] = cov
            C[a, a] = sill  # 自协方差

        C[:n, n] = 1.0
        C[n, :n] = 1.0

        # 右侧向量
        c0 = np.zeros(n + 1)
        for a in range(n):
            c0[a] = sill - self.model_func(np.array([local_dists[idx[a] if n_closest >= len(points) else a]]), nugget, sill, range_)[0]
        c0[a] = sill - self.model_func(local_dists[a:a+1], nugget, sill, range_)[0]
        # 重新计算c0
        for a in range(n):
            d = np.sqrt(np.sum((local_points[a] - target) ** 2))
            c0[a] = sill - self.model_func(np.array([d]), nugget, sill, range_)[0]
        c0[n] = 1.0

        try:
            weights = np.linalg.solve(C, c0)
            pred = float(np.dot(weights[:n], local_values))
            var = float(sill - np.dot(weights[:n], c0[:n]) - weights[n])
            var = max(var, 0.0)
        except np.linalg.LinAlgError:
            # 矩阵奇异，使用反距离加权
            w = 1.0 / (local_dists + 1e-10)
            w /= w.sum()
            pred = float(np.dot(w, local_values))
            var = float(np.var(local_values))

        return pred, var
