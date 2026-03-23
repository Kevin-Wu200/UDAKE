"""不确定性模型评估、校准评估与报告生成。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import ensure_1d, ensure_2d


@dataclass
class UQMetricResult:
    nll: float
    crps: float
    picp: float
    pinaw: float
    ece: float
    brier: float


def gaussian_nll(y_true: np.ndarray, pred_mean: np.ndarray, pred_var: np.ndarray) -> float:
    y = ensure_1d(y_true)
    m = ensure_1d(pred_mean)
    v = np.maximum(ensure_1d(pred_var), 1e-8)
    return float(np.mean(0.5 * np.log(2.0 * np.pi * v) + 0.5 * ((y - m) ** 2) / v))


def crps_gaussian(y_true: np.ndarray, pred_mean: np.ndarray, pred_var: np.ndarray) -> float:
    y = ensure_1d(y_true)
    m = ensure_1d(pred_mean)
    std = np.sqrt(np.maximum(ensure_1d(pred_var), 1e-8))
    z = (y - m) / std
    phi = np.exp(-0.5 * z ** 2) / np.sqrt(2.0 * np.pi)
    phi_cdf = 0.5 * (1.0 + np.vectorize(np.math.erf)(z / np.sqrt(2.0)))
    crps = std * (z * (2.0 * phi_cdf - 1.0) + 2.0 * phi - 1.0 / np.sqrt(np.pi))
    return float(np.mean(crps))


def prediction_interval(y_mean: np.ndarray, y_var: np.ndarray, confidence: float = 0.95) -> tuple[np.ndarray, np.ndarray]:
    z = 1.96 if confidence >= 0.95 else (1.645 if confidence >= 0.90 else 1.282)
    m = ensure_1d(y_mean)
    s = np.sqrt(np.maximum(ensure_1d(y_var), 1e-8))
    return m - z * s, m + z * s


def picp(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    y = ensure_1d(y_true)
    lo = ensure_1d(lower)
    hi = ensure_1d(upper)
    return float(np.mean((y >= lo) & (y <= hi)))


def pinaw(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    y = ensure_1d(y_true)
    lo = ensure_1d(lower)
    hi = ensure_1d(upper)
    width = np.mean(hi - lo)
    denom = float(np.max(y) - np.min(y) + 1e-8)
    return float(width / denom)


def expected_calibration_error(confidence: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> float:
    conf = ensure_1d(confidence)
    corr = ensure_1d(correct)
    bins = np.linspace(0.0, 1.0, int(max(2, n_bins)) + 1)
    total = len(conf)
    if total == 0:
        return 0.0

    ece = 0.0
    for i in range(len(bins) - 1):
        left, right = bins[i], bins[i + 1]
        mask = (conf >= left) & (conf < right if i < len(bins) - 2 else conf <= right)
        if np.any(mask):
            avg_conf = float(np.mean(conf[mask]))
            avg_acc = float(np.mean(corr[mask]))
            ece += abs(avg_conf - avg_acc) * float(np.sum(mask)) / total
    return float(ece)


def brier_score(probabilities: np.ndarray, labels: np.ndarray) -> float:
    probs = np.asarray(probabilities, dtype=float)
    y = ensure_1d(labels).astype(int)
    if probs.ndim == 1:
        probs = np.vstack([1.0 - probs, probs]).T
    n_classes = probs.shape[1]
    target = np.zeros_like(probs)
    target[np.arange(len(y)), y] = 1.0
    return float(np.mean(np.sum((probs - target) ** 2, axis=1)))


class UncertaintyEvaluator:
    def evaluate_regression(
        self,
        y_true: np.ndarray,
        pred_mean: np.ndarray,
        pred_var: np.ndarray,
        confidence: float = 0.95,
    ) -> UQMetricResult:
        y = ensure_1d(y_true)
        m = ensure_1d(pred_mean)
        v = np.maximum(ensure_1d(pred_var), 1e-8)
        lo, hi = prediction_interval(m, v, confidence=confidence)

        # 将回归区间覆盖转换为“校准正确性”用于 ECE 近似评估。
        conf = np.clip(1.0 - np.sqrt(v) / (np.sqrt(v).max() + 1e-8), 0.0, 1.0)
        corr = ((y >= lo) & (y <= hi)).astype(float)

        cls_prob = np.vstack([1.0 - conf, conf]).T
        cls_label = corr.astype(int)

        return UQMetricResult(
            nll=gaussian_nll(y, m, v),
            crps=crps_gaussian(y, m, v),
            picp=picp(y, lo, hi),
            pinaw=pinaw(y, lo, hi),
            ece=expected_calibration_error(conf, corr),
            brier=brier_score(cls_prob, cls_label),
        )

    def reliability_curve(
        self,
        confidence: np.ndarray,
        correct: np.ndarray,
        n_bins: int = 10,
    ) -> dict[str, np.ndarray]:
        conf = ensure_1d(confidence)
        corr = ensure_1d(correct)
        bins = np.linspace(0.0, 1.0, int(max(2, n_bins)) + 1)

        bin_conf = np.zeros(len(bins) - 1, dtype=float)
        bin_acc = np.zeros(len(bins) - 1, dtype=float)
        bin_count = np.zeros(len(bins) - 1, dtype=float)

        for i in range(len(bins) - 1):
            left, right = bins[i], bins[i + 1]
            mask = (conf >= left) & (conf < right if i < len(bins) - 2 else conf <= right)
            if np.any(mask):
                bin_conf[i] = float(np.mean(conf[mask]))
                bin_acc[i] = float(np.mean(corr[mask]))
                bin_count[i] = float(np.sum(mask))

        return {
            "bins": bins,
            "confidence": bin_conf,
            "accuracy": bin_acc,
            "count": bin_count,
        }

    def uncertainty_quality(
        self,
        pred_mean: np.ndarray,
        pred_var: np.ndarray,
        y_true: np.ndarray,
    ) -> dict[str, float]:
        y = ensure_1d(y_true)
        m = ensure_1d(pred_mean)
        v = np.maximum(ensure_1d(pred_var), 1e-8)
        std = np.sqrt(v)

        abs_err = np.abs(y - m)
        sharpness = float(np.mean(std))
        resolution = float(np.var(m))
        reliability = float(np.corrcoef(std, abs_err)[0, 1]) if np.std(std) > 1e-8 and np.std(abs_err) > 1e-8 else 0.0

        return {
            "sharpness": sharpness,
            "resolution": resolution,
            "reliability": reliability,
        }

    def uncertainty_visualizations(
        self,
        coords: np.ndarray,
        pred_mean: np.ndarray,
        pred_var: np.ndarray,
    ) -> dict[str, Any]:
        c = ensure_2d(coords)
        m = ensure_1d(pred_mean)
        v = np.maximum(ensure_1d(pred_var), 1e-8)
        if len(c) != len(m) or len(c) != len(v):
            raise ValueError("coords/pred_mean/pred_var 长度不一致")

        return {
            "uncertainty_map": [
                {"x": float(x), "y": float(y), "variance": float(var), "mean": float(mu)}
                for (x, y), mu, var in zip(c, m, v)
            ],
            "confidence_interval": {
                "lower": (m - 1.96 * np.sqrt(v)).tolist(),
                "upper": (m + 1.96 * np.sqrt(v)).tolist(),
            },
            "distribution": {
                "mean": float(np.mean(m)),
                "mean_std": float(np.std(m)),
                "var_mean": float(np.mean(v)),
                "var_std": float(np.std(v)),
            },
        }

    def benchmark_compare(
        self,
        y_true: np.ndarray,
        pred_mean: np.ndarray,
        pred_var: np.ndarray,
        kriging_var: np.ndarray,
        bootstrap_var: np.ndarray,
    ) -> dict[str, float]:
        y = ensure_1d(y_true)
        m = ensure_1d(pred_mean)
        v = np.maximum(ensure_1d(pred_var), 1e-8)
        kv = np.maximum(ensure_1d(kriging_var), 1e-8)
        bv = np.maximum(ensure_1d(bootstrap_var), 1e-8)

        nll_uq = gaussian_nll(y, m, v)
        nll_kriging = gaussian_nll(y, m, kv)
        nll_bootstrap = gaussian_nll(y, m, bv)

        delta_uq_vs_kriging = nll_kriging - nll_uq
        delta_uq_vs_bootstrap = nll_bootstrap - nll_uq

        # 近似配对 t 统计量
        loss_uq = 0.5 * np.log(2.0 * np.pi * v) + 0.5 * ((y - m) ** 2) / v
        loss_k = 0.5 * np.log(2.0 * np.pi * kv) + 0.5 * ((y - m) ** 2) / kv
        diff = loss_k - loss_uq
        std = np.std(diff, ddof=1) if len(diff) > 1 else 0.0
        t_stat = float(np.mean(diff) / (std / np.sqrt(len(diff)))) if std > 1e-8 else 0.0

        return {
            "nll_uq": float(nll_uq),
            "nll_kriging": float(nll_kriging),
            "nll_bootstrap": float(nll_bootstrap),
            "delta_uq_vs_kriging": float(delta_uq_vs_kriging),
            "delta_uq_vs_bootstrap": float(delta_uq_vs_bootstrap),
            "t_stat_uq_vs_kriging": t_stat,
        }

    def ablation_study(
        self,
        y_true: np.ndarray,
        pred_mean: np.ndarray,
        components: dict[str, np.ndarray],
    ) -> dict[str, float]:
        y = ensure_1d(y_true)
        m = ensure_1d(pred_mean)
        full_rmse = float(np.sqrt(np.mean((y - m) ** 2)))
        result = {"full": full_rmse}

        for name, comp in components.items():
            c = ensure_1d(comp)
            if len(c) != len(m):
                continue
            reduced = m - c
            rmse = float(np.sqrt(np.mean((y - reduced) ** 2)))
            result[name] = rmse
        return result

    def generate_report(
        self,
        metric: UQMetricResult,
        quality: dict[str, float],
        benchmark: dict[str, float] | None = None,
        ablation: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "metrics": metric.__dict__,
            "quality": quality,
            "benchmark": benchmark or {},
            "ablation": ablation or {},
        }

        lines = [
            "# 不确定性量化评估报告",
            "",
            "## 核心指标",
            f"- NLL: {metric.nll:.4f}",
            f"- CRPS: {metric.crps:.4f}",
            f"- PICP: {metric.picp:.4f}",
            f"- PINAW: {metric.pinaw:.4f}",
            f"- ECE: {metric.ece:.4f}",
            f"- Brier: {metric.brier:.4f}",
            "",
            "## 不确定性质量",
            f"- Sharpness: {quality.get('sharpness', 0.0):.4f}",
            f"- Resolution: {quality.get('resolution', 0.0):.4f}",
            f"- Reliability: {quality.get('reliability', 0.0):.4f}",
        ]
        if benchmark:
            lines += [
                "",
                "## 基准对比",
                f"- UQ vs Kriging (NLL 改善): {benchmark.get('delta_uq_vs_kriging', 0.0):.4f}",
                f"- UQ vs Bootstrap (NLL 改善): {benchmark.get('delta_uq_vs_bootstrap', 0.0):.4f}",
                f"- t-stat: {benchmark.get('t_stat_uq_vs_kriging', 0.0):.4f}",
            ]

        payload["markdown"] = "\n".join(lines)
        return payload
