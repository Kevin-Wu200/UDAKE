"""Evaluation and reporting for spatiotemporal forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class SpatioTemporalMetrics:
    rmse: float
    mae: float
    mape: float
    r2: float
    smape: float
    crps: float


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((t - p) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(t - p)))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    denom = np.maximum(np.abs(t), 1e-6)
    return float(np.mean(np.abs((t - p) / denom)) * 100.0)


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float).reshape(-1)
    p = np.asarray(y_pred, dtype=float).reshape(-1)
    ss_res = np.sum((t - p) ** 2)
    ss_tot = np.sum((t - np.mean(t)) ** 2)
    if ss_tot <= 1e-12:
        return 0.0
    return float(1.0 - ss_res / ss_tot)


def smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    denom = np.maximum(np.abs(t) + np.abs(p), 1e-6)
    return float(np.mean(2.0 * np.abs(t - p) / denom) * 100.0)


def crps_gaussian(y_true: np.ndarray, y_mean: np.ndarray, y_var: np.ndarray) -> float:
    t = np.asarray(y_true, dtype=float)
    m = np.asarray(y_mean, dtype=float)
    std = np.sqrt(np.maximum(np.asarray(y_var, dtype=float), 1e-8))
    z = (t - m) / std
    phi = np.exp(-0.5 * z ** 2) / np.sqrt(2.0 * np.pi)
    phi_cdf = 0.5 * (1.0 + np.vectorize(np.math.erf)(z / np.sqrt(2.0)))
    crps = std * (z * (2.0 * phi_cdf - 1.0) + 2.0 * phi - 1.0 / np.sqrt(np.pi))
    return float(np.mean(crps))


def evaluate_spatiotemporal_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_var: np.ndarray) -> SpatioTemporalMetrics:
    return SpatioTemporalMetrics(
        rmse=rmse(y_true, y_pred),
        mae=mae(y_true, y_pred),
        mape=mape(y_true, y_pred),
        r2=r2_score(y_true, y_pred),
        smape=smape(y_true, y_pred),
        crps=crps_gaussian(y_true, y_pred, y_var),
    )


def evaluate_time_dimension(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    """Per-horizon and cumulative temporal error metrics."""
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    if t.ndim == 1:
        t = t[None, :]
        p = p[None, :]

    per_step = [float(np.mean(np.abs(t[:, i] - p[:, i]))) for i in range(t.shape[1])]
    cumulative = np.cumsum(np.mean(np.abs(t - p), axis=0)).tolist()
    return {
        "per_step_mae": per_step,
        "cumulative_error": cumulative,
    }


def evaluate_spatial_dimension(y_true: np.ndarray, y_pred: np.ndarray, coords: np.ndarray, n_regions: int = 4) -> dict[str, Any]:
    """Region-wise and spatial consistency evaluation."""
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    c = np.asarray(coords, dtype=float)
    n = len(c)

    x_bins = np.linspace(float(c[:, 0].min()), float(c[:, 0].max()), n_regions + 1)
    region_mae: dict[str, float] = {}
    for i in range(n_regions):
        mask = (c[:, 0] >= x_bins[i]) & (c[:, 0] <= x_bins[i + 1] + 1e-12)
        if not np.any(mask):
            region_mae[f"region_{i}"] = 0.0
            continue
        region_mae[f"region_{i}"] = float(np.mean(np.abs(t[mask] - p[mask])))

    # Spatial consistency proxy: neighboring prediction differences.
    diff = c[:, None, :] - c[None, :, :]
    dist = np.sqrt(np.sum(diff ** 2, axis=-1) + 1e-8)
    close = dist < np.percentile(dist, 30)
    pred_mean = np.mean(p, axis=-1) if p.ndim == 2 else p
    spatial_consistency = float(np.mean(np.abs(pred_mean[:, None] - pred_mean[None, :])[close])) if np.any(close) else 0.0

    return {
        "region_mae": region_mae,
        "spatial_consistency": spatial_consistency,
        "node_count": int(n),
    }


def visualization_payload(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    coords: np.ndarray,
    attention_weights: np.ndarray | None = None,
) -> dict[str, Any]:
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    c = np.asarray(coords, dtype=float)
    error = np.abs(t - p)

    return {
        "prediction_sequence": p.tolist(),
        "ground_truth_sequence": t.tolist(),
        "error_heatmap": {
            "coords": c.tolist(),
            "error": np.mean(error, axis=-1).tolist() if error.ndim > 1 else error.tolist(),
        },
        "time_series_plot": {
            "step_mean_pred": np.mean(p, axis=0).tolist() if p.ndim > 1 else p.tolist(),
            "step_mean_true": np.mean(t, axis=0).tolist() if t.ndim > 1 else t.tolist(),
        },
        "attention_summary": None
        if attention_weights is None
        else {
            "mean": float(np.mean(attention_weights)),
            "max": float(np.max(attention_weights)),
            "min": float(np.min(attention_weights)),
        },
    }


def benchmark_comparison(y_true: np.ndarray, model_pred: np.ndarray, baselines: dict[str, np.ndarray]) -> dict[str, float]:
    scores = {"model": rmse(y_true, model_pred)}
    for name, pred in baselines.items():
        scores[name] = rmse(y_true, pred)
    return scores


def ablation_study(full_score: float, variants: dict[str, float]) -> dict[str, float]:
    return {name: float(score - full_score) for name, score in variants.items()}


def generate_report(
    metrics: SpatioTemporalMetrics,
    time_eval: dict[str, Any],
    spatial_eval: dict[str, Any],
    benchmark: dict[str, float],
    ablation: dict[str, float],
) -> dict[str, Any]:
    lines = [
        "# 时空预测评估报告",
        "",
        "## 核心指标",
        f"- RMSE: {metrics.rmse:.4f}",
        f"- MAE: {metrics.mae:.4f}",
        f"- MAPE: {metrics.mape:.4f}%",
        f"- R2: {metrics.r2:.4f}",
        f"- sMAPE: {metrics.smape:.4f}%",
        f"- CRPS: {metrics.crps:.4f}",
        "",
        "## 时间维度评估",
        f"- 步级误差: {time_eval.get('per_step_mae', [])}",
        f"- 累积误差: {time_eval.get('cumulative_error', [])}",
        "",
        "## 空间维度评估",
        f"- 区域误差: {spatial_eval.get('region_mae', {})}",
        f"- 空间一致性: {spatial_eval.get('spatial_consistency', 0.0):.4f}",
        "",
        "## 基准对比",
    ]
    for k, v in benchmark.items():
        lines.append(f"- {k}: {v:.4f}")

    lines.append("")
    lines.append("## 消融实验")
    for k, v in ablation.items():
        lines.append(f"- {k}: {v:+.4f}")

    return {
        "markdown": "\n".join(lines),
        "metrics": metrics.__dict__,
        "time": time_eval,
        "spatial": spatial_eval,
        "benchmark": benchmark,
        "ablation": ablation,
    }
