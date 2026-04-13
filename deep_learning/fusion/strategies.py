"""阶段7：融合策略实现。"""

from __future__ import annotations

import numpy as np

from .common import EPS, ModelPrediction, ensure_prediction_matrix, normalize_weights


class FusionStrategies:
    """融合策略集合。"""

    @staticmethod
    def _resolve_matrix(models: list[ModelPrediction], prediction_matrix: np.ndarray | None = None) -> np.ndarray:
        if prediction_matrix is None:
            return ensure_prediction_matrix(models)
        matrix = np.asarray(prediction_matrix, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != len(models):
            raise ValueError("prediction_matrix 维度与模型数量不一致")
        return matrix

    def simple_average(
        self,
        models: list[ModelPrediction],
        enable_uncertainty: bool = True,
        prediction_matrix: np.ndarray | None = None,
    ) -> tuple[list[float], list[float] | None]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        fused = np.mean(matrix, axis=0)
        var = np.var(matrix, axis=0, ddof=1) if enable_uncertainty and matrix.shape[0] > 1 else None
        return fused.tolist(), None if var is None else var.tolist()

    def weighted_average(
        self,
        models: list[ModelPrediction],
        weights: dict[str, float],
        enable_uncertainty: bool = True,
        prediction_matrix: np.ndarray | None = None,
    ) -> tuple[list[float], list[float] | None]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        norm = normalize_weights(weights, default_keys=[m.model_id for m in models])
        w = np.asarray([norm[m.model_id] for m in models], dtype=float)
        fused = np.average(matrix, axis=0, weights=w)

        var = None
        if enable_uncertainty:
            var = np.average((matrix - fused[None, :]) ** 2, axis=0, weights=w)
        return fused.tolist(), None if var is None else var.tolist()

    def median(
        self,
        models: list[ModelPrediction],
        enable_uncertainty: bool = True,
        prediction_matrix: np.ndarray | None = None,
    ) -> tuple[list[float], list[float] | None]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        fused = np.median(matrix, axis=0)
        var = None
        if enable_uncertainty:
            q25 = np.percentile(matrix, 25, axis=0)
            q75 = np.percentile(matrix, 75, axis=0)
            # 用 IQR 近似 sigma，再转为方差。
            sigma = (q75 - q25) / 1.35
            var = np.maximum(sigma ** 2, EPS)
        return fused.tolist(), None if var is None else var.tolist()

    def max_min(
        self,
        models: list[ModelPrediction],
        enable_uncertainty: bool = True,
        prediction_matrix: np.ndarray | None = None,
    ) -> tuple[list[float], list[float] | None]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        max_pred = np.max(matrix, axis=0)
        min_pred = np.min(matrix, axis=0)
        fused = 0.5 * (max_pred + min_pred)

        var = None
        if enable_uncertainty:
            sigma = np.maximum((max_pred - min_pred) / 4.0, EPS)
            var = sigma ** 2
        return fused.tolist(), None if var is None else var.tolist()

    def stacking(
        self,
        models: list[ModelPrediction],
        weights: dict[str, float],
        true_values: list[float] | None,
        n_folds: int = 5,
        enable_uncertainty: bool = True,
        prediction_matrix: np.ndarray | None = None,
    ) -> tuple[list[float], list[float] | None, dict[str, float]]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)

        if true_values is None or len(true_values) != matrix.shape[1] or matrix.shape[1] < 3:
            fused, var = self.weighted_average(
                models,
                weights,
                enable_uncertainty=enable_uncertainty,
                prediction_matrix=matrix,
            )
            return fused, var, normalize_weights(weights, default_keys=[m.model_id for m in models])

        y = np.asarray(true_values, dtype=float)
        n_samples = matrix.shape[1]
        n_models = matrix.shape[0]
        folds = int(max(2, min(n_folds, n_samples)))

        # K 折学习元权重，防止单次拟合过拟合。
        fold_weights: list[np.ndarray] = []
        indices = np.arange(n_samples)
        splits = np.array_split(indices, folds)

        for fold_idx in range(folds):
            val_idx = splits[fold_idx]
            if len(val_idx) == 0:
                continue
            train_idx = np.setdiff1d(indices, val_idx)
            if len(train_idx) <= n_models:
                continue

            x_train = matrix[:, train_idx].T
            y_train = y[train_idx]
            coef, *_ = np.linalg.lstsq(x_train, y_train, rcond=None)
            coef = np.maximum(coef, 0.0)
            total = float(np.sum(coef))
            if total <= EPS:
                coef = np.ones(n_models, dtype=float) / n_models
            else:
                coef = coef / total
            fold_weights.append(coef)

        if not fold_weights:
            base = normalize_weights(weights, default_keys=[m.model_id for m in models])
            coef = np.asarray([base[m.model_id] for m in models], dtype=float)
        else:
            coef = np.mean(np.vstack(fold_weights), axis=0)
            coef = coef / np.clip(np.sum(coef), EPS, None)

        fused = coef @ matrix
        var = None
        if enable_uncertainty:
            var = np.average((matrix - fused[None, :]) ** 2, axis=0, weights=coef)

        learned = {m.model_id: float(coef[idx]) for idx, m in enumerate(models)}
        return fused.tolist(), None if var is None else var.tolist(), learned

    def bayesian_model_average(
        self,
        models: list[ModelPrediction],
        posterior_weights: dict[str, float],
        enable_uncertainty: bool = True,
        prediction_matrix: np.ndarray | None = None,
    ) -> tuple[list[float], list[float] | None]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        norm = normalize_weights(posterior_weights, default_keys=[m.model_id for m in models])
        w = np.asarray([norm[m.model_id] for m in models], dtype=float)

        fused = np.average(matrix, axis=0, weights=w)
        var = None

        if enable_uncertainty:
            if all(m.variances is not None for m in models):
                model_vars = np.asarray([m.variances for m in models], dtype=float)
                total = np.sum(w[:, None] * (model_vars + (matrix - fused[None, :]) ** 2), axis=0)
                var = np.maximum(total, EPS)
            else:
                var = np.average((matrix - fused[None, :]) ** 2, axis=0, weights=w)

        return fused.tolist(), None if var is None else var.tolist()

    def variance_weighted(
        self,
        models: list[ModelPrediction],
        fallback_weights: dict[str, float],
        enable_uncertainty: bool = True,
        prediction_matrix: np.ndarray | None = None,
    ) -> tuple[list[float], list[float] | None]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        if not all(m.variances is not None for m in models):
            return self.weighted_average(
                models,
                fallback_weights,
                enable_uncertainty=enable_uncertainty,
                prediction_matrix=matrix,
            )

        model_vars = np.asarray([m.variances for m in models], dtype=float)
        inv_var = 1.0 / np.clip(model_vars, EPS, None)
        denom = np.clip(np.sum(inv_var, axis=0), EPS, None)
        local_w = inv_var / denom[None, :]

        fused = np.sum(local_w * matrix, axis=0)
        var = None
        if enable_uncertainty:
            var = 1.0 / denom
        return fused.tolist(), None if var is None else var.tolist()

    def dynamic(
        self,
        models: list[ModelPrediction],
        base_weights: dict[str, float],
        context: dict[str, list[float]] | None = None,
        enable_uncertainty: bool = True,
        prediction_matrix: np.ndarray | None = None,
    ) -> tuple[list[float], list[float] | None, dict[str, list[float]]]:
        matrix = self._resolve_matrix(models, prediction_matrix=prediction_matrix)
        n_models, n_points = matrix.shape
        norm = normalize_weights(base_weights, default_keys=[m.model_id for m in models])
        base = np.asarray([norm[m.model_id] for m in models], dtype=float)

        model_vars = None
        if all(m.variances is not None for m in models):
            model_vars = np.asarray([m.variances for m in models], dtype=float)

        difficulty = None
        if context and "difficulty" in context:
            difficulty = np.asarray(context["difficulty"], dtype=float)
            if len(difficulty) != n_points:
                difficulty = None

        fused = np.zeros(n_points, dtype=float)
        var = np.zeros(n_points, dtype=float)
        dynamic_weights: list[np.ndarray] = []

        for i in range(n_points):
            point_pred = matrix[:, i]
            disagreement = np.abs(point_pred - np.mean(point_pred))
            if model_vars is not None:
                reliability = 1.0 / np.clip(model_vars[:, i], EPS, None)
            else:
                reliability = 1.0 / np.clip(disagreement + EPS, EPS, None)

            diff_scale = 1.0
            if difficulty is not None:
                diff_scale = float(np.clip(difficulty[i], 0.2, 5.0))

            score = np.log(np.clip(base, EPS, None)) + np.log(np.clip(reliability, EPS, None)) / diff_scale
            score = score - np.max(score)
            local = np.exp(score)
            local = local / np.clip(np.sum(local), EPS, None)
            dynamic_weights.append(local)

            fused[i] = float(np.sum(local * point_pred))
            var[i] = float(np.sum(local * (point_pred - fused[i]) ** 2))

        diagnostics = {m.model_id: [float(w[idx]) for w in dynamic_weights] for idx, m in enumerate(models)}
        return fused.tolist(), var.tolist() if enable_uncertainty else None, diagnostics
