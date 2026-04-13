"""阶段7：融合模型评估与监控指标。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .common import EPS, FusionResult, ModelMetric, ModelPrediction, ensure_prediction_matrix


@dataclass
class BootstrapStability:
    rmse_mean: float
    rmse_std: float
    stability_score: float


class FusionEvaluator:
    """融合效果评估器。"""

    def _resolve_matrix(self, models: list[ModelPrediction], prediction_matrix: np.ndarray | None = None) -> np.ndarray:
        if prediction_matrix is None:
            return ensure_prediction_matrix(models)
        matrix = np.asarray(prediction_matrix, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != len(models):
            raise ValueError("prediction_matrix 维度与模型数量不一致")
        return matrix

    def evaluate_model_metrics(
        self,
        models: list[ModelPrediction],
        true_values: list[float] | None,
        prediction_matrix: np.ndarray | None = None,
    ) -> list[ModelMetric]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        if true_values is None:
            return [
                ModelMetric(
                    model_id=m.model_id,
                    rmse=0.0,
                    mae=0.0,
                    r2=1.0,
                    mape=0.0,
                    stability=self._stability(matrix[idx]),
                    uncertainty=self._uncertainty_proxy(m),
                )
                for idx, m in enumerate(models)
            ]

        y = np.asarray(true_values, dtype=float)
        if len(y) != matrix.shape[1]:
            raise ValueError("真实值长度与预测不一致")

        metrics: list[ModelMetric] = []
        for idx, model in enumerate(models):
            pred = matrix[idx]
            rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
            mae = float(np.mean(np.abs(pred - y)))
            denom = np.clip(np.abs(y), EPS, None)
            mape = float(np.mean(np.abs((pred - y) / denom)) * 100.0)
            ss_res = float(np.sum((y - pred) ** 2))
            ss_tot = float(np.sum((y - np.mean(y)) ** 2))
            r2 = float(1.0 - ss_res / (ss_tot + EPS))
            r2 = float(np.clip(r2, -1.0, 1.0))

            metrics.append(
                ModelMetric(
                    model_id=model.model_id,
                    rmse=rmse,
                    mae=mae,
                    r2=r2,
                    mape=mape,
                    stability=self._stability(pred),
                    uncertainty=self._uncertainty_proxy(model),
                )
            )

        return metrics

    def evaluate_fusion(self, fused: list[float], true_values: list[float] | None) -> dict[str, float]:
        if true_values is None:
            return {}

        y = np.asarray(true_values, dtype=float)
        pred = np.asarray(fused, dtype=float)
        if len(y) != len(pred):
            raise ValueError("融合结果长度与真实值不一致")

        rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
        mae = float(np.mean(np.abs(pred - y)))
        ss_res = float(np.sum((y - pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = float(1.0 - ss_res / (ss_tot + EPS))
        r2 = float(np.clip(r2, -1.0, 1.0))

        denom = np.clip(np.abs(y), EPS, None)
        mape = float(np.mean(np.abs((pred - y) / denom)) * 100.0)
        max_error = float(np.max(np.abs(pred - y)))

        return {
            "rmse": rmse,
            "mae": mae,
            "r2": r2,
            "mape": mape,
            "max_error": max_error,
        }

    def compute_improvement(
        self,
        model_metrics: list[ModelMetric],
        fused_metrics: dict[str, float],
    ) -> dict[str, float]:
        if not model_metrics or not fused_metrics:
            return {}

        avg_rmse = float(np.mean([m.rmse for m in model_metrics]))
        avg_mae = float(np.mean([m.mae for m in model_metrics]))
        avg_r2 = float(np.mean([m.r2 for m in model_metrics]))

        best_rmse = min(m.rmse for m in model_metrics)
        best_mae = min(m.mae for m in model_metrics)
        best_r2 = max(m.r2 for m in model_metrics)

        out: dict[str, float] = {}
        if avg_rmse > EPS:
            out["rmse_vs_avg_pct"] = float((avg_rmse - fused_metrics.get("rmse", avg_rmse)) / avg_rmse * 100.0)
        if avg_mae > EPS:
            out["mae_vs_avg_pct"] = float((avg_mae - fused_metrics.get("mae", avg_mae)) / avg_mae * 100.0)
        out["r2_vs_avg"] = float(fused_metrics.get("r2", avg_r2) - avg_r2)

        if best_rmse > EPS:
            out["rmse_vs_best_pct"] = float((best_rmse - fused_metrics.get("rmse", best_rmse)) / best_rmse * 100.0)
        if best_mae > EPS:
            out["mae_vs_best_pct"] = float((best_mae - fused_metrics.get("mae", best_mae)) / best_mae * 100.0)
        out["r2_vs_best"] = float(fused_metrics.get("r2", best_r2) - best_r2)
        return out

    def bootstrap_stability(
        self,
        models: list[ModelPrediction],
        true_values: list[float],
        fuse_fn: Callable[[list[ModelPrediction], list[int]], list[float]],
        n_bootstrap: int = 50,
    ) -> BootstrapStability:
        n = len(true_values)
        y = np.asarray(true_values, dtype=float)
        if n == 0:
            return BootstrapStability(0.0, 0.0, 0.0)

        rng = np.random.default_rng(42)
        rmse_list: list[float] = []

        for _ in range(max(1, int(n_bootstrap))):
            idx = rng.integers(0, n, size=n)
            pred = np.asarray(fuse_fn(models, idx.tolist()), dtype=float)
            target = y[idx]
            if len(pred) != len(target):
                continue
            rmse = float(np.sqrt(np.mean((pred - target) ** 2)))
            rmse_list.append(rmse)

        if not rmse_list:
            return BootstrapStability(0.0, 0.0, 0.0)

        mean = float(np.mean(rmse_list))
        std = float(np.std(rmse_list))
        stability = float(1.0 / (1.0 + std / (mean + EPS)))
        return BootstrapStability(rmse_mean=mean, rmse_std=std, stability_score=stability)

    def diversity_metrics(self, models: list[ModelPrediction], prediction_matrix: np.ndarray | None = None) -> dict[str, float]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        n_models = matrix.shape[0]
        if n_models <= 1:
            return {"correlation_diversity": 0.0, "prediction_spread": 0.0, "ensemble_diversity": 0.0}

        corr_vals: list[float] = []
        for i in range(n_models):
            for j in range(i + 1, n_models):
                c = np.corrcoef(matrix[i], matrix[j])[0, 1]
                if np.isnan(c):
                    c = 1.0
                corr_vals.append(abs(float(c)))

        avg_abs_corr = float(np.mean(corr_vals)) if corr_vals else 1.0
        spread = float(np.mean(np.std(matrix, axis=0)))

        return {
            "correlation_diversity": float(1.0 - avg_abs_corr),
            "prediction_spread": spread,
            "ensemble_diversity": float(0.5 * (1.0 - avg_abs_corr) + 0.5 * min(1.0, spread)),
        }

    def uncertainty_metrics(
        self,
        result: FusionResult,
        true_values: list[float] | None,
        z_score: float = 1.96,
    ) -> dict[str, float]:
        if result.fused_variances is None:
            return {"uncertainty_available": 0.0}

        var = np.asarray(result.fused_variances, dtype=float)
        sigma = np.sqrt(np.clip(var, EPS, None))
        mean_sigma = float(np.mean(sigma))
        ci_width = float(np.mean(2.0 * z_score * sigma))

        coverage = 0.0
        if true_values is not None and len(true_values) == len(result.fused_predictions):
            y = np.asarray(true_values, dtype=float)
            pred = np.asarray(result.fused_predictions, dtype=float)
            lower = pred - z_score * sigma
            upper = pred + z_score * sigma
            coverage = float(np.mean((y >= lower) & (y <= upper)))

        return {
            "uncertainty_available": 1.0,
            "mean_sigma": mean_sigma,
            "mean_ci_width": ci_width,
            "ci_coverage": coverage,
        }

    def _stability(self, values: np.ndarray, window_size: int = 5) -> float:
        if len(values) < window_size:
            return 1.0
        vars_ = [float(np.var(values[i : i + window_size])) for i in range(len(values) - window_size + 1)]
        avg_var = float(np.mean(vars_)) if vars_ else 0.0
        return float(1.0 / (1.0 + avg_var))

    def _uncertainty_proxy(self, model: ModelPrediction) -> float:
        if model.variances:
            return float(np.mean(np.asarray(model.variances, dtype=float)))
        pred = np.asarray(model.predictions, dtype=float)
        return float(np.var(pred))
