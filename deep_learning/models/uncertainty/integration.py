"""不确定性量化模块与现有系统集成。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from deep_learning.utils.cache import CacheManager

from .aggregation import UncertaintyAggregator
from .common import ensure_1d, ensure_2d
from .training_pipeline import UQTrainingConfig, UQTrainingManager


@dataclass
class IntegratedUQResult:
    mean: np.ndarray
    variance: np.ndarray
    aleatoric: np.ndarray
    epistemic: np.ndarray
    method: str


class UncertaintySystemIntegrator:
    """对接 realtime_interpolation 与 uncertainty_dashboard 的轻量适配器。"""

    def __init__(self, cache_ttl_seconds: int = 180) -> None:
        self.cache = CacheManager(ttl_seconds=cache_ttl_seconds)
        self.aggregator = UncertaintyAggregator()
        self.training_manager = UQTrainingManager()
        self.models: dict[str, Any] = {}

    def _nearest_interpolate(self, sample_coords: np.ndarray, sample_values: np.ndarray, query_coords: np.ndarray) -> np.ndarray:
        sc = ensure_2d(sample_coords)
        sv = ensure_1d(sample_values)
        qc = ensure_2d(query_coords)
        diff = qc[:, None, :] - sc[None, :, :]
        dist = np.sqrt(np.sum(diff ** 2, axis=-1) + 1e-8)
        idx = np.argmin(dist, axis=1)
        return sv[idx]

    def _build_features(self, sample_coords: np.ndarray, sample_values: np.ndarray, query_coords: np.ndarray) -> np.ndarray:
        base_mean = self._nearest_interpolate(sample_coords, sample_values, query_coords)
        sc = ensure_2d(sample_coords)
        qc = ensure_2d(query_coords)
        diff = qc[:, None, :] - sc[None, :, :]
        dist = np.sqrt(np.sum(diff ** 2, axis=-1) + 1e-8)
        min_dist = np.min(dist, axis=1)
        return np.concatenate([qc, base_mean.reshape(-1, 1), min_dist.reshape(-1, 1)], axis=1)

    def train_uq_model(
        self,
        model_name: str,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        max_epochs: int = 160,
    ) -> dict[str, Any]:
        sc = ensure_2d(sample_coords)
        sv = ensure_1d(sample_values)
        # 训练/推理统一特征构造，避免维度不一致。
        features = self._build_features(sc, sv, sc)

        cfg = UQTrainingConfig(model_name=model_name, max_epochs=max_epochs)
        payload = self.training_manager.train(cfg, features, sv)
        self.models[model_name] = payload["model"]
        return payload

    def predict(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray,
        method: str = "deep_ensemble",
    ) -> IntegratedUQResult:
        sc = ensure_2d(sample_coords)
        sv = ensure_1d(sample_values)
        qc = ensure_2d(query_coords)

        cache_key = f"uq:{method}:{hash(sc.tobytes())}:{hash(sv.tobytes())}:{hash(qc.tobytes())}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if method not in self.models:
            self.train_uq_model(method, sc, sv)

        model = self.models[method]
        query_features = self._build_features(sc, sv, qc)

        if method == "edl":
            out = model.predict(query_features)
            probs = np.asarray(out["probabilities"], dtype=float)
            confidence = np.asarray(out["confidence"], dtype=float)
            variance = np.maximum(1.0 - confidence, 1e-6)
            mean = np.argmax(probs, axis=1).astype(float)
            aleatoric = np.asarray(out["uncertainty"]["data"], dtype=float)
            epistemic = np.asarray(out["uncertainty"]["knowledge"], dtype=float)
        elif method == "deep_ensemble":
            out = model.predict(query_features, aggregation="mean")
            mean = np.asarray(out["mean"], dtype=float)
            variance = np.asarray(out["variance"], dtype=float)
            aleatoric = np.asarray(out["aleatoric"], dtype=float)
            epistemic = np.asarray(out["epistemic"], dtype=float)
        elif method == "mc_dropout":
            out = model.predict(query_features, t=40)
            mean = np.asarray(out["mean"], dtype=float)
            variance = np.asarray(out["variance"], dtype=float)
            aleatoric = np.asarray(out["aleatoric"], dtype=float)
            epistemic = np.asarray(out["epistemic"], dtype=float)
        else:
            out = model.predict(query_features, num_samples=40)
            mean = np.asarray(out["mean"], dtype=float)
            variance = np.asarray(out["variance"], dtype=float)
            aleatoric = np.asarray(out["aleatoric"], dtype=float)
            epistemic = np.asarray(out["epistemic"], dtype=float)

        result = IntegratedUQResult(
            mean=mean,
            variance=np.maximum(variance, 1e-8),
            aleatoric=np.maximum(aleatoric, 1e-8),
            epistemic=np.maximum(epistemic, 1e-8),
            method=method,
        )
        self.cache.set(cache_key, result)
        return result

    def fuse_with_existing_uncertainty(
        self,
        uq_result: IntegratedUQResult,
        legacy_variance: np.ndarray,
        blend_ratio: float = 0.7,
    ) -> IntegratedUQResult:
        legacy = np.maximum(ensure_1d(legacy_variance), 1e-8)
        if len(legacy) != len(uq_result.variance):
            raise ValueError("legacy_variance 长度不匹配")

        ratio = float(np.clip(blend_ratio, 0.0, 1.0))
        variance = ratio * uq_result.variance + (1.0 - ratio) * legacy
        epistemic = ratio * uq_result.epistemic
        aleatoric = np.maximum(variance - epistemic, 1e-8)
        return IntegratedUQResult(
            mean=uq_result.mean,
            variance=np.maximum(variance, 1e-8),
            aleatoric=aleatoric,
            epistemic=np.maximum(epistemic, 1e-8),
            method=f"{uq_result.method}+legacy",
        )

    def api_predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.predict(
            sample_coords=np.asarray(payload["sample_coords"], dtype=float),
            sample_values=np.asarray(payload["sample_values"], dtype=float),
            query_coords=np.asarray(payload["query_coords"], dtype=float),
            method=str(payload.get("method", "deep_ensemble")),
        )

        var = result.variance
        levels = {
            "low": float(np.mean(var <= np.percentile(var, 33))),
            "medium": float(np.mean((var > np.percentile(var, 33)) & (var <= np.percentile(var, 66)))),
            "high": float(np.mean(var > np.percentile(var, 66))),
        }

        return {
            "prediction": result.mean.tolist(),
            "variance": result.variance.tolist(),
            "aleatoric": result.aleatoric.tolist(),
            "epistemic": result.epistemic.tolist(),
            "uncertainty_levels": levels,
            "method": result.method,
        }

    def dashboard_payload(self, coords: np.ndarray, uq_result: IntegratedUQResult) -> dict[str, Any]:
        c = ensure_2d(coords)
        decomp = self.aggregator.spatial_uncertainty_decomposition(c, uq_result.variance)
        return {
            "points": [
                {
                    "x": float(x),
                    "y": float(y),
                    "mean": float(m),
                    "variance": float(v),
                    "aleatoric": float(a),
                    "epistemic": float(e),
                }
                for (x, y), m, v, a, e in zip(c, uq_result.mean, uq_result.variance, uq_result.aleatoric, uq_result.epistemic)
            ],
            "spatial_decomposition": {
                "local_mean": decomp["local_mean"].tolist(),
                "local_std": decomp["local_std"].tolist(),
                "spatial_residual": decomp["spatial_residual"].tolist(),
            },
        }

    def realtime_updates(self, stream_batches: list[dict[str, np.ndarray]], method: str = "mc_dropout") -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = []
        for i, batch in enumerate(stream_batches):
            res = self.predict(
                sample_coords=batch["sample_coords"],
                sample_values=batch["sample_values"],
                query_coords=batch["query_coords"],
                method=method,
            )
            outputs.append(
                {
                    "batch_index": i,
                    "method": res.method,
                    "mean_uncertainty": float(np.mean(res.variance)),
                    "max_uncertainty": float(np.max(res.variance)),
                    "min_uncertainty": float(np.min(res.variance)),
                }
            )
        return outputs
