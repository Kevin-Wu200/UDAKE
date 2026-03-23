"""Loss functions for spatial interpolation tasks."""

from __future__ import annotations

import numpy as np


def mse_loss(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    pred = np.asarray(y_pred, dtype=float).reshape(-1)
    true = np.asarray(y_true, dtype=float).reshape(-1)
    return float(np.mean((pred - true) ** 2))


def mae_loss(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    pred = np.asarray(y_pred, dtype=float).reshape(-1)
    true = np.asarray(y_true, dtype=float).reshape(-1)
    return float(np.mean(np.abs(pred - true)))


def gaussian_nll_loss(y_pred: np.ndarray, y_var: np.ndarray, y_true: np.ndarray) -> float:
    pred = np.asarray(y_pred, dtype=float).reshape(-1)
    var = np.maximum(np.asarray(y_var, dtype=float).reshape(-1), 1e-8)
    true = np.asarray(y_true, dtype=float).reshape(-1)
    nll = 0.5 * np.log(var) + 0.5 * ((true - pred) ** 2) / var
    return float(np.mean(nll))


def gradient_smoothness_loss(values: np.ndarray, adjacency: np.ndarray) -> float:
    pred = np.asarray(values, dtype=float).reshape(-1)
    adj = np.asarray(adjacency, dtype=float)
    if adj.size == 0:
        return 0.0
    diff = pred[:, None] - pred[None, :]
    smooth = adj * (diff ** 2)
    return float(np.sum(smooth) / np.maximum(np.sum(adj), 1e-8))


def physical_constraint_loss(
    values: np.ndarray,
    min_value: float | None = None,
    max_value: float | None = None,
    monotonic_axis: np.ndarray | None = None,
) -> float:
    pred = np.asarray(values, dtype=float).reshape(-1)
    penalty = 0.0

    if min_value is not None:
        penalty += float(np.mean(np.maximum(0.0, min_value - pred) ** 2))
    if max_value is not None:
        penalty += float(np.mean(np.maximum(0.0, pred - max_value) ** 2))

    if monotonic_axis is not None and len(pred) > 1:
        axis = np.asarray(monotonic_axis, dtype=float).reshape(-1)
        order = np.argsort(axis)
        ordered = pred[order]
        monotonic_violation = np.maximum(0.0, ordered[:-1] - ordered[1:])
        penalty += float(np.mean(monotonic_violation ** 2))

    return penalty


def combined_spatial_loss(
    y_pred: np.ndarray,
    y_true: np.ndarray,
    y_var: np.ndarray,
    adjacency: np.ndarray,
    weights: dict[str, float] | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    monotonic_axis: np.ndarray | None = None,
) -> dict[str, float]:
    w = {
        "mse": 1.0,
        "mae": 0.3,
        "nll": 0.5,
        "smooth": 0.1,
        "physical": 0.1,
    }
    if weights:
        w.update(weights)

    comp_mse = mse_loss(y_pred, y_true)
    comp_mae = mae_loss(y_pred, y_true)
    comp_nll = gaussian_nll_loss(y_pred, y_var, y_true)
    comp_smooth = gradient_smoothness_loss(y_pred, adjacency)
    comp_phy = physical_constraint_loss(y_pred, min_value=min_value, max_value=max_value, monotonic_axis=monotonic_axis)

    total = (
        w["mse"] * comp_mse
        + w["mae"] * comp_mae
        + w["nll"] * comp_nll
        + w["smooth"] * comp_smooth
        + w["physical"] * comp_phy
    )
    return {
        "total": float(total),
        "mse": float(comp_mse),
        "mae": float(comp_mae),
        "nll": float(comp_nll),
        "smooth": float(comp_smooth),
        "physical": float(comp_phy),
    }
