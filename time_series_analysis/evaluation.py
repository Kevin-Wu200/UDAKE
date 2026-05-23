"""
时序预测评估模块
"""

from typing import Dict, Optional

import numpy as np


def evaluate_forecast(
    actual: np.ndarray,
    predicted: np.ndarray,
    lower_bound: Optional[np.ndarray] = None,
    upper_bound: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """
    评估预测结果

    Args:
        actual: 实际值
        predicted: 预测值
        lower_bound: 下置信界
        upper_bound: 上置信界

    Returns:
        Dict: 评估指标
    """
    actual = np.array(actual, dtype=np.float64)
    predicted = np.array(predicted, dtype=np.float64)

    mask = ~np.isnan(actual) & ~np.isnan(predicted)
    actual = actual[mask]
    predicted = predicted[mask]

    if len(actual) == 0:
        return {
            'rmse': float('inf'),
            'mae': float('inf'),
            'mape': float('inf'),
            'r2': 0.0,
            'coverage': 0.0,
        }

    errors = actual - predicted
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    mae = float(np.mean(np.abs(errors)))

    # MAPE
    mape = float(np.mean(np.abs(errors / (actual + 1e-10))) * 100)

    # R²
    ss_res = np.sum(errors ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    # 置信区间覆盖率
    coverage = 0.0
    if lower_bound is not None and upper_bound is not None:
        lower = np.array(lower_bound, dtype=np.float64)[mask]
        upper = np.array(upper_bound, dtype=np.float64)[mask]
        coverage = float(np.mean((actual >= lower) & (actual <= upper)))

    return {
        'rmse': rmse,
        'mae': mae,
        'mape': mape,
        'r2': r2,
        'coverage': coverage,
    }
