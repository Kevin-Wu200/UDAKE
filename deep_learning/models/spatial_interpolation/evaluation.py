"""Evaluation and comparison toolkit for spatial interpolation models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class MetricResult:
    rmse: float
    mae: float
    r2: float
    mape: float
    crps: float


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float).reshape(-1)
    p = np.asarray(y_pred, dtype=float).reshape(-1)
    return float(np.sqrt(np.mean((t - p) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float).reshape(-1)
    p = np.asarray(y_pred, dtype=float).reshape(-1)
    return float(np.mean(np.abs(t - p)))


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float).reshape(-1)
    p = np.asarray(y_pred, dtype=float).reshape(-1)
    ss_res = np.sum((t - p) ** 2)
    ss_tot = np.sum((t - np.mean(t)) ** 2)
    if ss_tot <= 1e-12:
        return 0.0
    return float(1.0 - ss_res / ss_tot)


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float).reshape(-1)
    p = np.asarray(y_pred, dtype=float).reshape(-1)
    denom = np.maximum(np.abs(t), 1e-6)
    return float(np.mean(np.abs((t - p) / denom)) * 100.0)


def crps_gaussian(y_true: np.ndarray, y_mean: np.ndarray, y_var: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float).reshape(-1)
    m = np.asarray(y_mean, dtype=float).reshape(-1)
    std = np.sqrt(np.maximum(np.asarray(y_var, dtype=float).reshape(-1), 1e-8))
    z = (t - m) / std

    # Approximate CRPS for Gaussian predictive distribution.
    # crps = sigma * [z*(2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi)]
    phi = np.exp(-0.5 * z ** 2) / np.sqrt(2.0 * np.pi)
    phi_cdf = 0.5 * (1.0 + np.vectorize(np.math.erf)(z / np.sqrt(2.0)))
    crps = std * (z * (2.0 * phi_cdf - 1.0) + 2.0 * phi - 1.0 / np.sqrt(np.pi))
    return float(np.mean(crps))


def evaluate_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_var: np.ndarray) -> MetricResult:
    return MetricResult(
        rmse=rmse(y_true, y_pred),
        mae=mae(y_true, y_pred),
        r2=r2_score(y_true, y_pred),
        mape=mape(y_true, y_pred),
        crps=crps_gaussian(y_true, y_pred, y_var),
    )


def prediction_comparison(y_true: np.ndarray, candidates: dict[str, np.ndarray]) -> dict[str, float]:
    return {name: rmse(y_true, pred) for name, pred in candidates.items()}


def error_heatmap_values(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return np.abs(np.asarray(y_true, dtype=float).reshape(-1) - np.asarray(y_pred, dtype=float).reshape(-1))


def uncertainty_summary(y_var: np.ndarray) -> dict[str, float]:
    var = np.asarray(y_var, dtype=float).reshape(-1)
    return {
        "mean": float(np.mean(var)),
        "std": float(np.std(var)),
        "p95": float(np.percentile(var, 95)),
    }


def attention_summary(attn: np.ndarray) -> dict[str, float]:
    arr = np.asarray(attn, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "max": float(np.max(arr)),
        "min": float(np.min(arr)),
    }


def paired_t_stat(sample_a: np.ndarray, sample_b: np.ndarray) -> float:
    a = np.asarray(sample_a, dtype=float).reshape(-1)
    b = np.asarray(sample_b, dtype=float).reshape(-1)
    d = a - b
    mean = float(np.mean(d))
    std = float(np.std(d, ddof=1)) if len(d) > 1 else 0.0
    if std <= 1e-12:
        return 0.0
    return mean / (std / np.sqrt(len(d)))


def ablation_contribution(full_score: float, ablated_scores: dict[str, float]) -> dict[str, float]:
    return {name: float(score - full_score) for name, score in ablated_scores.items()}


def hyperparam_sensitivity(records: list[dict[str, Any]], metric_key: str = "rmse") -> dict[str, float]:
    if not records:
        return {}
    keys = [k for k in records[0].keys() if k != metric_key]
    result: dict[str, float] = {}
    metric_values = np.asarray([float(r[metric_key]) for r in records], dtype=float)

    for key in keys:
        vals = np.asarray([float(r[key]) for r in records], dtype=float)
        if np.std(vals) < 1e-12:
            result[key] = 0.0
            continue
        corr = np.corrcoef(vals, metric_values)[0, 1]
        result[key] = float(corr)
    return result


def generate_evaluation_report(
    metrics: MetricResult,
    baseline_metrics: MetricResult,
    ablation: dict[str, float],
    t_stat: float,
) -> dict[str, Any]:
    return {
        "metrics": metrics.__dict__,
        "baseline": baseline_metrics.__dict__,
        "improvement": {
            "rmse": float(baseline_metrics.rmse - metrics.rmse),
            "mae": float(baseline_metrics.mae - metrics.mae),
            "crps": float(baseline_metrics.crps - metrics.crps),
        },
        "ablation": ablation,
        "significance_t_stat": float(t_stat),
    }
