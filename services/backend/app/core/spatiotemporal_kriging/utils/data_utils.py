"""数据处理工具。"""

from __future__ import annotations

from typing import Dict, List

import numpy as np


def normalize_series(series: Dict[str, List[float]]) -> Dict[str, List[float]]:
    """对 x/y/z/t/value 进行 min-max 归一化。"""
    normalized: Dict[str, List[float]] = {}
    for key, values in series.items():
        arr = np.asarray(values, dtype=float)
        if arr.size == 0:
            normalized[key] = []
            continue
        min_v = float(np.min(arr))
        max_v = float(np.max(arr))
        span = max(max_v - min_v, 1e-8)
        normalized[key] = ((arr - min_v) / span).tolist()
    return normalized
