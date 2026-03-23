"""Loss functions for spatiotemporal forecasting."""

from __future__ import annotations

import numpy as np


def mse_loss(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    p = np.asarray(y_pred, dtype=float)
    t = np.asarray(y_true, dtype=float)
    return float(np.mean((p - t) ** 2))


def mae_loss(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    p = np.asarray(y_pred, dtype=float)
    t = np.asarray(y_true, dtype=float)
    return float(np.mean(np.abs(p - t)))


def quantile_loss(y_pred: np.ndarray, y_true: np.ndarray, quantile: float = 0.5) -> float:
    p = np.asarray(y_pred, dtype=float)
    t = np.asarray(y_true, dtype=float)
    q = float(np.clip(quantile, 0.01, 0.99))
    err = t - p
    return float(np.mean(np.maximum(q * err, (q - 1.0) * err)))


def temporal_consistency_loss(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    """Compare temporal gradients between prediction and target."""
    p = np.asarray(y_pred, dtype=float)
    t = np.asarray(y_true, dtype=float)
    if p.ndim < 2:
        return 0.0
    dp = np.diff(p, axis=-1)
    dt = np.diff(t, axis=-1)
    return float(np.mean((dp - dt) ** 2))


def spatial_consistency_loss(y_pred: np.ndarray, adjacency: np.ndarray) -> float:
    """Encourage nearby nodes to have smooth forecasts."""
    p = np.asarray(y_pred, dtype=float)
    if p.ndim == 1:
        p = p[:, None]
    adj = np.asarray(adjacency, dtype=float)
    if adj.size == 0:
        return 0.0
    diff = p[:, None, :] - p[None, :, :]
    sq = np.sum(diff ** 2, axis=-1)
    return float(np.sum(adj * sq) / np.maximum(np.sum(adj), 1e-8))


def gaussian_nll(y_mean: np.ndarray, y_var: np.ndarray, y_true: np.ndarray) -> float:
    m = np.asarray(y_mean, dtype=float)
    v = np.maximum(np.asarray(y_var, dtype=float), 1e-8)
    t = np.asarray(y_true, dtype=float)
    nll = 0.5 * np.log(v) + 0.5 * ((t - m) ** 2) / v
    return float(np.mean(nll))


def combined_spatiotemporal_loss(
    y_pred: np.ndarray,
    y_true: np.ndarray,
    y_var: np.ndarray,
    adjacency: np.ndarray,
    quantile: float = 0.5,
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    w = {
        "mse": 1.0,
        "mae": 0.4,
        "quantile": 0.3,
        "temporal": 0.3,
        "spatial": 0.25,
        "nll": 0.4,
    }
    if weights:
        w.update(weights)

    c_mse = mse_loss(y_pred, y_true)
    c_mae = mae_loss(y_pred, y_true)
    c_q = quantile_loss(y_pred, y_true, quantile=quantile)
    c_t = temporal_consistency_loss(y_pred, y_true)
    c_s = spatial_consistency_loss(y_pred, adjacency)
    c_nll = gaussian_nll(y_pred, y_var, y_true)
    total = (
        w["mse"] * c_mse
        + w["mae"] * c_mae
        + w["quantile"] * c_q
        + w["temporal"] * c_t
        + w["spatial"] * c_s
        + w["nll"] * c_nll
    )
    return {
        "total": float(total),
        "mse": float(c_mse),
        "mae": float(c_mae),
        "quantile": float(c_q),
        "temporal": float(c_t),
        "spatial": float(c_s),
        "nll": float(c_nll),
    }
