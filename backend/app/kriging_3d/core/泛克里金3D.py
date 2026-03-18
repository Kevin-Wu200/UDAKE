"""
3D泛克里金引擎
支持线性和二次趋势
"""
import numpy as np
from typing import Dict, Any, Optional, List
from .变异函数3D import Variogram3D
from .距离计算 import Distance3D
import logging

logger = logging.getLogger(__name__)


class UniversalKriging3D:
    """3D泛克里金插值引擎"""

    def __init__(self):
        self.variogram_params = None
        self.model_func = None

    def _build_drift_matrix(self, coords: np.ndarray, drift_terms: List[str]) -> np.ndarray:
        """
        构建漂移矩阵
        drift_terms: ['linear_x', 'linear_y', 'linear_z', 'quadratic']
        """
        n = len(coords)
        columns = []
        for term in drift_terms:
            if term == "linear_x":
                columns.append(coords[:, 0])
            elif term == "linear_y":
                columns.append(coords[:, 1])
            elif term == "linear_z":
                columns.append(coords[:, 2])
            elif term == "quadratic":
                columns.append(coords[:, 0] ** 2)
                columns.append(coords[:, 1] ** 2)
                columns.append(coords[:, 2] ** 2)
                columns.append(coords[:, 0] * coords[:, 1])
                columns.append(coords[:, 0] * coords[:, 2])
                columns.append(coords[:, 1] * coords[:, 2])
            elif term == "regional_linear":
                columns.append(coords[:, 0])
                columns.append(coords[:, 1])
                columns.append(coords[:, 2])
        if not columns:
            columns.append(coords[:, 0])
            columns.append(coords[:, 1])
            columns.append(coords[:, 2])
        return np.column_stack(columns)

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
        drift_terms: Optional[List[str]] = None,
        anisotropy_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """执行3D泛克里金插值"""
        if drift_terms is None:
            drift_terms = ["regional_linear"]

        # 趋势检测与去除
        drift_matrix = self._build_drift_matrix(points, drift_terms)
        trend_coeffs, _, _, _ = np.linalg.lstsq(
            np.column_stack([np.ones(len(points)), drift_matrix]),
            values, rcond=None
        )
        trend_values = np.column_stack([np.ones(len(points)), drift_matrix]) @ trend_coeffs
        residuals = values - trend_values

        # 对残差拟合变异函数
        lags, sv, counts = Variogram3D.compute_experimental(
            points, residuals, nlags, anisotropy_params=anisotropy_params
        )
        vario_result = Variogram3D.fit(lags, sv, variogram_model, counts)
        self.variogram_params = vario_result
        model_type = vario_result["model_type"]
        nugget = vario_result["nugget"]
        sill = vario_result["sill"]
        range_ = vario_result["range"]
        self.model_func = Variogram3D.MODELS[model_type]

        logger.info(f"泛克里金变异函数: {model_type}, nugget={nugget:.4f}, sill={sill:.4f}, range={range_:.4f}")

        nx, ny, nz = len(grid_x), len(grid_y), len(grid_z)
        prediction = np.zeros((nx, ny, nz))
        variance = np.zeros((nx, ny, nz))
        n_drift = drift_matrix.shape[1]

        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    target = np.array([grid_x[i], grid_y[j], grid_z[k]])
                    pred, var = self._kriging_at_point(
                        target, points, residuals, nugget, sill, range_,
                        n_closest, drift_terms, n_drift, trend_coeffs
                    )
                    prediction[i, j, k] = pred
                    variance[i, j, k] = var

            if (i + 1) % max(1, nx // 10) == 0:
                progress = (i + 1) / nx * 100
                logger.info(f"泛克里金进度: {progress:.1f}%")

        return {
            "prediction": prediction,
            "variance": variance,
            "variogram": vario_result,
            "trend_coefficients": trend_coeffs.tolist(),
            "grid_x": grid_x.tolist(),
            "grid_y": grid_y.tolist(),
            "grid_z": grid_z.tolist(),
        }

    def _kriging_at_point(
        self,
        target: np.ndarray,
        points: np.ndarray,
        residuals: np.ndarray,
        nugget: float,
        sill: float,
        range_: float,
        n_closest: int,
        drift_terms: List[str],
        n_drift: int,
        trend_coeffs: np.ndarray
    ) -> tuple:
        """在单个目标点执行泛克里金估计"""
        dists = np.sqrt(np.sum((points - target) ** 2, axis=1))
        if n_closest < len(points):
            idx = np.argpartition(dists, n_closest)[:n_closest]
        else:
            idx = np.arange(len(points))

        local_points = points[idx]
        local_residuals = residuals[idx]
        n = len(idx)

        # 构建扩展克里金方程组: (n + 1 + n_drift) x (n + 1 + n_drift)
        m = n + 1 + n_drift
        C = np.zeros((m, m))

        # 协方差矩阵
        for a in range(n):
            for b in range(a + 1, n):
                d = np.sqrt(np.sum((local_points[a] - local_points[b]) ** 2))
                cov = sill - self.model_func(np.array([d]), nugget, sill, range_)[0]
                C[a, b] = cov
                C[b, a] = cov
            C[a, a] = sill

        # 拉格朗日乘子约束
        C[:n, n] = 1.0
        C[n, :n] = 1.0

        # 漂移约束
        local_drift = self._build_drift_matrix(local_points, drift_terms)
        for d_idx in range(n_drift):
            C[:n, n + 1 + d_idx] = local_drift[:, d_idx]
            C[n + 1 + d_idx, :n] = local_drift[:, d_idx]

        # 右侧向量
        c0 = np.zeros(m)
        for a in range(n):
            d = np.sqrt(np.sum((local_points[a] - target) ** 2))
            c0[a] = sill - self.model_func(np.array([d]), nugget, sill, range_)[0]
        c0[n] = 1.0

        target_drift = self._build_drift_matrix(target.reshape(1, -1), drift_terms)
        for d_idx in range(n_drift):
            c0[n + 1 + d_idx] = target_drift[0, d_idx]

        try:
            weights = np.linalg.solve(C, c0)
            # 残差估计
            residual_pred = float(np.dot(weights[:n], local_residuals))
            # 趋势估计
            target_full = np.concatenate([[1.0], target_drift[0]])
            trend_pred = float(np.dot(target_full, trend_coeffs))
            pred = residual_pred + trend_pred
            var = float(sill - np.dot(weights[:n], c0[:n]) - weights[n])
            var = max(var, 0.0)
        except np.linalg.LinAlgError:
            local_dists = dists[idx]
            w = 1.0 / (local_dists + 1e-10)
            w /= w.sum()
            pred = float(np.dot(w, local_residuals))
            target_full = np.concatenate([[1.0], target_drift[0]])
            pred += float(np.dot(target_full, trend_coeffs))
            var = float(np.var(local_residuals))

        return pred, var
