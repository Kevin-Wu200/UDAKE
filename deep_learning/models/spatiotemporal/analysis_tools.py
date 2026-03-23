"""Time-series analysis toolkit for stage-6 spatiotemporal module."""

from __future__ import annotations

import numpy as np


def moving_average(x: np.ndarray, window: int = 7) -> np.ndarray:
    arr = np.asarray(x, dtype=float).reshape(-1)
    w = max(2, int(window))
    kernel = np.ones(w, dtype=float) / w
    return np.convolve(arr, kernel, mode="same")


def seasonal_decompose(series: np.ndarray, period: int = 12) -> dict[str, np.ndarray]:
    """Simple trend-seasonal-residual decomposition."""
    x = np.asarray(series, dtype=float).reshape(-1)
    trend = moving_average(x, window=max(3, period))

    seasonal = np.zeros_like(x)
    p = max(2, int(period))
    for i in range(p):
        idx = np.arange(i, len(x), p)
        seasonal[idx] = np.mean(x[idx] - trend[idx]) if len(idx) > 0 else 0.0

    residual = x - trend - seasonal
    return {"trend": trend, "seasonal": seasonal, "residual": residual}


def adf_proxy_test(series: np.ndarray) -> dict[str, float | bool]:
    """ADF-like proxy: based on lag-1 difference variance reduction."""
    x = np.asarray(series, dtype=float).reshape(-1)
    dx = np.diff(x)
    if len(dx) < 3:
        return {"statistic": 0.0, "p_value": 1.0, "stationary": False}
    stat = float(np.var(dx) - np.var(x[1:]))
    p_value = float(np.exp(-abs(stat)))
    return {"statistic": stat, "p_value": p_value, "stationary": bool(p_value < 0.12)}


def kpss_proxy_test(series: np.ndarray) -> dict[str, float | bool]:
    """KPSS-like proxy: trend strength as non-stationarity signal."""
    x = np.asarray(series, dtype=float).reshape(-1)
    t = np.arange(len(x), dtype=float)
    if len(x) < 4:
        return {"statistic": 0.0, "p_value": 1.0, "stationary": True}

    coeff = np.polyfit(t, x, deg=1)
    trend = coeff[0] * t + coeff[1]
    resid = x - trend
    stat = float(np.var(trend) / np.maximum(np.var(resid), 1e-8))
    p_value = float(np.exp(-stat))
    return {"statistic": stat, "p_value": p_value, "stationary": bool(p_value > 0.08)}


def acf(series: np.ndarray, max_lag: int = 20) -> np.ndarray:
    x = np.asarray(series, dtype=float).reshape(-1)
    x = x - np.mean(x)
    denom = np.sum(x ** 2)
    lags = min(max_lag, len(x) - 1)
    out = np.zeros(lags + 1, dtype=float)
    out[0] = 1.0
    for lag in range(1, lags + 1):
        out[lag] = np.sum(x[:-lag] * x[lag:]) / np.maximum(denom, 1e-8)
    return out


def pacf(series: np.ndarray, max_lag: int = 20) -> np.ndarray:
    x = np.asarray(series, dtype=float).reshape(-1)
    lags = min(max_lag, len(x) - 1)
    out = np.zeros(lags + 1, dtype=float)
    out[0] = 1.0

    for lag in range(1, lags + 1):
        y = x[lag:]
        design = np.stack([x[lag - j - 1 : len(x) - j - 1] for j in range(lag)], axis=1)
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
        out[lag] = float(beta[-1])
    return out


def cross_correlation(series_a: np.ndarray, series_b: np.ndarray, max_lag: int = 20) -> dict[str, np.ndarray]:
    a = np.asarray(series_a, dtype=float).reshape(-1)
    b = np.asarray(series_b, dtype=float).reshape(-1)
    n = min(len(a), len(b))
    a = a[:n] - np.mean(a[:n])
    b = b[:n] - np.mean(b[:n])

    lags = np.arange(-max_lag, max_lag + 1)
    corr = np.zeros_like(lags, dtype=float)
    denom = np.sqrt(np.sum(a ** 2) * np.sum(b ** 2)) + 1e-8

    for i, lag in enumerate(lags):
        if lag < 0:
            corr[i] = np.sum(a[-lag:] * b[: n + lag]) / denom
        elif lag > 0:
            corr[i] = np.sum(a[: n - lag] * b[lag:]) / denom
        else:
            corr[i] = np.sum(a * b) / denom
    return {"lags": lags, "correlation": corr}


def fft_spectrum(series: np.ndarray, sample_rate: float = 1.0) -> dict[str, np.ndarray]:
    x = np.asarray(series, dtype=float).reshape(-1)
    spec = np.fft.rfft(x)
    freq = np.fft.rfftfreq(len(x), d=1.0 / max(sample_rate, 1e-6))
    amp = np.abs(spec)
    return {"frequency": freq, "amplitude": amp}


def detect_temporal_anomalies(series: np.ndarray, z_threshold: float = 3.0) -> dict[str, np.ndarray]:
    x = np.asarray(series, dtype=float).reshape(-1)
    mu = float(np.mean(x))
    sigma = float(np.std(x) + 1e-8)
    z = (x - mu) / sigma
    idx = np.where(np.abs(z) > z_threshold)[0]
    return {"indices": idx, "z_score": z}


def detect_spatiotemporal_anomalies(values: np.ndarray, adjacency: np.ndarray, threshold: float = 2.5) -> dict[str, np.ndarray]:
    """values shape [n_nodes, seq_len] or [n_nodes, seq_len, feat]."""
    v = np.asarray(values, dtype=float)
    if v.ndim == 3:
        v = v[:, :, 0]
    adj = np.asarray(adjacency, dtype=float)

    neigh_sum = adj @ v
    degree = np.maximum(np.sum(adj, axis=1, keepdims=True), 1e-8)
    neigh_mean = neigh_sum / degree
    residual = v - neigh_mean

    mu = np.mean(residual)
    sigma = np.std(residual) + 1e-8
    score = np.abs((residual - mu) / sigma)
    idx = np.argwhere(score > threshold)
    return {"indices": idx, "score": score}
