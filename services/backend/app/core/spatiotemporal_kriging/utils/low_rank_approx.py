"""低秩近似工具。"""

from __future__ import annotations

import numpy as np


def truncated_svd(matrix: np.ndarray, rank: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回截断 SVD 结果。"""
    if rank <= 0:
        raise ValueError("rank 必须大于 0")
    u, s, vt = np.linalg.svd(matrix, full_matrices=False)
    r = min(rank, len(s))
    return u[:, :r], s[:r], vt[:r, :]
