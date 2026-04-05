"""矩阵工具函数。"""

from __future__ import annotations

import numpy as np


def stable_cholesky_solve(a: np.ndarray, b: np.ndarray, jitter: float = 1e-8) -> np.ndarray:
    """稳定的 Cholesky 求解，失败时自动增加抖动项。"""
    eye = np.eye(a.shape[0], dtype=a.dtype)
    current = float(jitter)
    for _ in range(6):
        try:
            l = np.linalg.cholesky(a + current * eye)
            y = np.linalg.solve(l, b)
            return np.linalg.solve(l.T, y)
        except np.linalg.LinAlgError:
            current *= 10
    return np.linalg.solve(a + current * eye, b)
