"""深度学习服务编排层。"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import os
from typing import Any
import time
import tempfile

import numpy as np

from ai_extension.异常检测模块 import DeepAnomalyFusionDetector
from deep_learning.inference import BatchPredictor
from deep_learning.fusion.service import fusion_platform_service
from deep_learning.models.anomaly_detection import AnomalyTrainingConfig, AnomalyTrainingManager
from deep_learning.models import AttentionKrigingModel, GNNKrigingModel, ModelRegistry, ResidualKrigingModel
from deep_learning.models.sampling_rl import SamplingRLIntegrator
from deep_learning.models.spatial_interpolation import SpatialInterpolationIntegrator
from deep_learning.models.spatiotemporal import SpatioTemporalSystemIntegrator, SpatioTemporalTrainingConfig
from deep_learning.training import LightningTrainer, SpatialTrainingConfig, TrainingConfig, train_spatial_model
from deep_learning.utils.device import DeviceManager
from deep_learning.utils.monitoring import AlertManager, AlertRule, MetricMonitor, SystemResourceMonitor
from .anomaly_cache import AnomalyModelCache
from .anomaly_features import AnomalyFeatureRegistry
from .attention_kriging_explainer import AttentionKrigingLIMEAdapter, AttentionKrigingSHAPAdapter
from .contrastive_anomaly_explainer import ContrastiveLimeAdapter, ContrastiveShapAdapter
from .gcae_anomaly_explainer import GCAELimeAdapter, GCAEShapAdapter
from .gan_anomaly_explainer import GANAnomalyLimeAdapter, GANAnomalySHAPAdapter
from .gnn_kriging_explainer import GNNKrigingLIMEAdapter, GNNKrigingSHAPAdapter
from .lime_explainer import SpatiotemporalLIMEExplainer
from .parallel_runtime import ParallelExecutionManager, ParallelTask
from .shap_explainer import SpatiotemporalSHAPExplainer
from .vae_anomaly_explainer import VAEAnomalyLIMEAdapter, VAEAnomalySHAPAdapter


@dataclass
class DummyRegressor:
    """用于基础架构验证的轻量模型。"""

    bias: float = 0.0

    def train_step(self, batch: list[list[float]], lr: float = 0.01, mixed_precision: bool = False) -> float:
        del mixed_precision
        if not batch:
            return 0.0
        targets = [float(item[-1]) for item in batch]
        pred = [self.bias for _ in batch]
        grad = sum((p - t) for p, t in zip(pred, targets)) / len(batch)
        self.bias -= lr * grad
        return abs(grad)

    def val_step(self, batch: list[list[float]]) -> float:
        if not batch:
            return 0.0
        targets = [float(item[-1]) for item in batch]
        pred = [self.bias for _ in batch]
        error = sum(abs(p - t) for p, t in zip(pred, targets)) / len(batch)
        return float(error)

    def predict(self, batch: list[list[float]]) -> list[float]:
        return [self.bias for _ in batch]

    def get_state(self) -> dict[str, float]:
        return {"bias": self.bias}

    def load_state(self, state: dict[str, Any]) -> None:
        self.bias = float(state.get("bias", 0.0))


class DeepLearningService:
    def __init__(self) -> None:
        self.registry = ModelRegistry()
        self.registry.register("dummy_regressor", lambda: DummyRegressor())
        self.registry.register("gnn_kriging", lambda: GNNKrigingModel(hidden_dim=16))
        self.registry.register("attention_kriging", lambda: AttentionKrigingModel(dim=24))
        self.registry.register("residual_kriging", lambda: ResidualKrigingModel(architecture="hybrid"))

        self.metric_monitor = MetricMonitor()
        self.resource_monitor = SystemResourceMonitor()
        self.alert_manager = AlertManager([AlertRule(metric="val_loss", threshold=1.0, operator=">=")])
        self.device_manager = DeviceManager()
        self.integrator = SpatialInterpolationIntegrator(cache_ttl_seconds=300)
        self.anomaly_training = AnomalyTrainingManager()
        self.anomaly_models: dict[str, Any] = {}
        self.deep_fusion = DeepAnomalyFusionDetector()
        self.sampling_rl_integrators: dict[str, SamplingRLIntegrator] = {}
        self.spatiotemporal_integrator = SpatioTemporalSystemIntegrator(cache_ttl_seconds=180)
        self._spatiotemporal_model_cache: dict[str, dict[str, Any]] = {}
        self.fusion_platform = fusion_platform_service
        self.lime_explainer = SpatiotemporalLIMEExplainer()
        self.shap_explainer = SpatiotemporalSHAPExplainer()
        self.anomaly_feature_registry = AnomalyFeatureRegistry()
        self.vae_lime_adapter = VAEAnomalyLIMEAdapter()
        self.vae_shap_adapter = VAEAnomalySHAPAdapter()
        self.gcae_lime_adapter = GCAELimeAdapter()
        self.gcae_shap_adapter = GCAEShapAdapter()
        self.gan_lime_adapter = GANAnomalyLimeAdapter()
        self.gan_shap_adapter = GANAnomalySHAPAdapter()
        self.gnn_kriging_lime_adapter = GNNKrigingLIMEAdapter()
        self.gnn_kriging_shap_adapter = GNNKrigingSHAPAdapter()
        self.attention_kriging_lime_adapter = AttentionKrigingLIMEAdapter()
        self.attention_kriging_shap_adapter = AttentionKrigingSHAPAdapter()
        self.contrastive_lime_adapter = ContrastiveLimeAdapter()
        self.contrastive_shap_adapter = ContrastiveShapAdapter()
        cache_file = os.path.join(tempfile.gettempdir(), f"udake_anomaly_cache_{os.getpid()}.json")
        self.anomaly_cache = AnomalyModelCache(
            cache_size=256,
            ttl_seconds=600,
            persist_path=cache_file,
            enable_compression=True,
            compression_threshold_bytes=1024,
        )
        self._anomaly_model_versions: dict[str, int] = {}
        self.batch_parallel = ParallelExecutionManager(name="st-batch", max_workers=4, min_workers=1)

    @staticmethod
    def _hash_array(value: np.ndarray) -> str:
        arr = np.ascontiguousarray(np.asarray(value))
        return hashlib.sha256(arr.tobytes()).hexdigest()

    @staticmethod
    def _stable_hash(payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _bump_anomaly_model_version(self, model_name: str) -> None:
        current = int(self._anomaly_model_versions.get(model_name, 0))
        self._anomaly_model_versions[model_name] = current + 1

    def _model_version(self, model_name: str) -> int:
        return int(self._anomaly_model_versions.get(model_name, 0))

    def _cache_prefix(self, namespace: str, model_name: str, model_version: int) -> str:
        return f"{namespace}:{model_name}:v{int(model_version)}:"

    def _prediction_cache_key(
        self,
        *,
        model_name: str,
        model_version: int,
        coords: np.ndarray,
        values: np.ndarray,
        threshold_method: str,
        percentile: float,
        k: float,
    ) -> str:
        digest = self._stable_hash(
            {
                "coords_shape": [int(coords.shape[0]), int(coords.shape[1])],
                "coords_hash": self._hash_array(coords),
                "values_hash": self._hash_array(values),
                "threshold_method": threshold_method,
                "percentile": float(percentile),
                "k": float(k),
            }
        )
        return f"{self._cache_prefix('prediction', model_name, model_version)}{digest}"

    def _explanation_cache_key(
        self,
        *,
        model_name: str,
        model_version: int,
        coords: np.ndarray,
        values: np.ndarray,
        method: str,
        top_k: int,
        include_prediction: bool,
        num_samples: int | None,
        nsamples: int | None,
        max_explain_nodes: int,
    ) -> str:
        digest = self._stable_hash(
            {
                "coords_shape": [int(coords.shape[0]), int(coords.shape[1])],
                "coords_hash": self._hash_array(coords),
                "values_hash": self._hash_array(values),
                "method": method,
                "top_k": int(top_k),
                "include_prediction": bool(include_prediction),
                "num_samples": num_samples,
                "nsamples": nsamples,
                "max_explain_nodes": int(max_explain_nodes),
            }
        )
        return f"{self._cache_prefix('explanation', model_name, model_version)}{digest}"

    def _with_cache_meta(self, payload: dict[str, Any], *, namespace: str, cache_hit: bool) -> dict[str, Any]:
        result = copy.deepcopy(payload)
        result["cache"] = {
            "namespace": namespace,
            "cache_hit": bool(cache_hit),
            "stats": self.anomaly_cache.stats(),
        }
        return result

    def health(self) -> dict[str, Any]:
        profile = self.device_manager.configure()
        return {
            "status": "healthy",
            "device": profile.device,
            "cuda_available": profile.cuda_available,
            "mps_available": profile.mps_available,
            "registered_models": self.registry.list_models(),
            "trained_anomaly_models": sorted(self.anomaly_models.keys()),
            "trained_sampling_rl_models": sorted(self.sampling_rl_integrators.keys()),
            "trained_spatiotemporal_models": sorted(self.spatiotemporal_integrator.training_records.keys()),
            "fusion_profiles": self.fusion_platform.model_registry_status().get("profiles", []),
        }

    def train_demo_model(self, samples: list[list[float]]) -> dict[str, Any]:
        model = self.registry.create("dummy_regressor")
        trainer = LightningTrainer(
            TrainingConfig(
                max_epochs=30,
                learning_rate=0.05,
                early_stopping_patience=5,
                lr_decay=0.95,
                mixed_precision=True,
            )
        )
        # 使用同一批样本作为 train/val，目标是验证训练链路可运行。
        result = trainer.train(model, [samples], [samples])
        self.metric_monitor.log("val_loss", float(result["best_val_loss"]))
        alerts = self.alert_manager.evaluate({"val_loss": float(result["best_val_loss"])})
        return {"training": result, "alerts": alerts}

    def predict(self, samples: list[list[float]], bias: float = 0.0) -> dict[str, Any]:
        model = DummyRegressor(bias=bias)
        predictor = BatchPredictor(model=model)
        preds = predictor.predict(samples)
        self.metric_monitor.log("inference_count", float(len(samples)))
        return {
            "predictions": preds,
            "resource": self.resource_monitor.collect(),
        }

    def _to_spatial_arrays(self, samples: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
        if not samples:
            raise ValueError("samples cannot be empty")
        arr = np.asarray(samples, dtype=float)
        if arr.ndim != 2 or arr.shape[1] < 3:
            raise ValueError("samples must be [[x, y, value], ...]")
        coords = arr[:, :2]
        values = arr[:, 2]
        return coords, values

    def _validate_coords_values(self, coords: list[list[float]], values: list[float]) -> tuple[np.ndarray, np.ndarray]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [[x, y], ...]")
        if len(c) != len(v):
            raise ValueError("coords and values length mismatch")
        if len(c) < 5:
            raise ValueError("at least 5 points are required")
        return c, v

    def _validate_uncertainty_map(self, uncertainty_map: list[list[float]]) -> np.ndarray:
        arr = np.asarray(uncertainty_map, dtype=float)
        if arr.ndim != 2:
            raise ValueError("uncertainty_map must be 2D matrix")
        if arr.shape[0] < 4 or arr.shape[1] < 4:
            raise ValueError("uncertainty_map size must be >= 4x4")
        return np.clip(arr, 1e-6, 1.0)

    def _validate_spatiotemporal_inputs(
        self,
        coords: list[list[float]],
        series: list[list[list[float]]],
        pred_horizon: int,
    ) -> tuple[np.ndarray, np.ndarray, int]:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(series, dtype=float)
        horizon = int(max(1, pred_horizon))
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [[x, y], ...]")
        if s.ndim != 3:
            raise ValueError("series must be [n_nodes, seq_len, n_features]")
        if s.shape[0] != c.shape[0]:
            raise ValueError("coords and series node count mismatch")
        if s.shape[1] < max(4, horizon):
            raise ValueError("series length is too short")
        return c, s, horizon

    def _is_usable_anomaly_model(self, model: Any) -> bool:
        return model is not None and callable(getattr(model, "predict", None))

    def _get_or_train_anomaly_model(
        self,
        model_name: str,
        coords: list[list[float]],
        values: list[float],
        epochs: int = 15,
    ) -> Any:
        model = self.anomaly_models.get(model_name)
        if not self._is_usable_anomaly_model(model):
            self.train_anomaly_model(model_name, coords, values, epochs=epochs)
            model = self.anomaly_models.get(model_name)
        if not self._is_usable_anomaly_model(model):
            raise RuntimeError(f"anomaly model unavailable: {model_name}")
        return model

    def _get_sampling_rl_integrator(self, model_name: str) -> SamplingRLIntegrator:
        if model_name not in {"ppo", "dqn", "a2c", "a3c"}:
            raise ValueError("model_name must be one of ppo/dqn/a2c/a3c")
        if model_name not in self.sampling_rl_integrators:
            self.sampling_rl_integrators[model_name] = SamplingRLIntegrator(model_name=model_name)  # type: ignore[arg-type]
        return self.sampling_rl_integrators[model_name]

    def train_sampling_rl(
        self,
        model_name: str,
        uncertainty_map: list[list[float]],
        existing_points: list[list[float]] | None = None,
        episodes: int = 30,
        budget: int = 20,
    ) -> dict[str, Any]:
        arr = self._validate_uncertainty_map(uncertainty_map)
        points = np.asarray(existing_points, dtype=float) if existing_points else None

        integrator = self._get_sampling_rl_integrator(model_name)
        result = integrator.train(
            uncertainty_map=arr,
            existing_points=points,
            episodes=max(5, int(episodes)),
            budget=max(8, int(budget)),
        )

        summary = result.get("summary", {})
        self.metric_monitor.log(f"{model_name}_sampling_rl_reward", float(summary.get("final_reward", 0.0)))
        return {
            "model_name": model_name,
            "training": result,
            "resource": self.resource_monitor.collect(),
        }

    def recommend_sampling_rl(
        self,
        model_name: str,
        uncertainty_map: list[list[float]],
        existing_points: list[list[float]] | None = None,
        n_recommendations: int = 10,
        fusion_strategy: str = "hybrid",
        realtime: bool = True,
    ) -> dict[str, Any]:
        arr = self._validate_uncertainty_map(uncertainty_map)
        points = np.asarray(existing_points, dtype=float) if existing_points else None

        if fusion_strategy not in {"rl_only", "rule_only", "hybrid"}:
            raise ValueError("fusion_strategy must be one of rl_only/rule_only/hybrid")

        integrator = self._get_sampling_rl_integrator(model_name)
        if not integrator.latest_training:
            integrator.train(arr, existing_points=points, episodes=15, budget=max(10, n_recommendations * 2))

        result = integrator.recommend(
            uncertainty_map=arr,
            existing_points=points,
            n_recommendations=max(1, int(n_recommendations)),
            fusion_strategy=fusion_strategy,  # type: ignore[arg-type]
            realtime=bool(realtime),
        )
        optimize = integrator.optimize_strategy(arr)
        self.metric_monitor.log(f"{model_name}_sampling_rl_recommend_count", float(len(result.get("recommendations", []))))

        return {
            "model_name": model_name,
            "recommendation": result,
            "optimization": optimize,
            "resource": self.resource_monitor.collect(),
        }

    def train_anomaly_model(
        self,
        model_name: str,
        coords: list[list[float]],
        values: list[float],
        epochs: int = 30,
    ) -> dict[str, Any]:
        c, v = self._validate_coords_values(coords, values)
        if model_name not in {"vae", "gcae", "gan", "contrastive"}:
            raise ValueError("model_name must be one of vae/gcae/gan/contrastive")

        payload = self.anomaly_training.train(
            AnomalyTrainingConfig(model_name=model_name, max_epochs=max(5, int(epochs))),  # type: ignore[arg-type]
            c,
            v,
        )
        self.anomaly_models[model_name] = payload["model"]
        self.invalidate_anomaly_cache(model_name=model_name)
        self._bump_anomaly_model_version(model_name)
        self.metric_monitor.log(f"{model_name}_train", float(payload["training"].get("best_total_loss", payload["training"].get("final_loss", 0.0))))
        return {
            "model_name": model_name,
            "training": payload["training"],
            "config": payload["config"],
        }

    def predict_anomaly(
        self,
        model_name: str,
        coords: list[list[float]],
        values: list[float],
        threshold_method: str = "percentile",
        percentile: float = 95.0,
        k: float = 2.5,
    ) -> dict[str, Any]:
        c, v = self._validate_coords_values(coords, values)
        if model_name not in {"vae", "gcae", "gan", "contrastive", "fusion"}:
            raise ValueError("model_name must be one of vae/gcae/gan/contrastive/fusion")
        if model_name != "fusion":
            _ = self._get_or_train_anomaly_model(model_name, coords, values, epochs=15)

        model_version = self._model_version(model_name)
        predict_cache_key = self._prediction_cache_key(
            model_name=model_name,
            model_version=model_version,
            coords=c,
            values=v,
            threshold_method=threshold_method,
            percentile=percentile,
            k=k,
        )
        cached_prediction = self.anomaly_cache.get("prediction", predict_cache_key)
        if cached_prediction is not None:
            self.metric_monitor.log(f"{model_name}_prediction_cache_hit", 1.0)
            return self._with_cache_meta(cached_prediction, namespace="prediction", cache_hit=True)

        if model_name == "fusion":
            x = c[:, 0]
            y = c[:, 1]
            result = self.deep_fusion.detect(x, y, v, threshold_method=threshold_method, percentile=percentile)
            self.metric_monitor.log("fusion_anomaly_count", float(result["anomaly_count"]))
            self.anomaly_cache.set("prediction", predict_cache_key, result)
            self.metric_monitor.log("fusion_prediction_cache_hit", 0.0)
            return self._with_cache_meta(result, namespace="prediction", cache_hit=False)

        model = self._get_or_train_anomaly_model(model_name, coords, values, epochs=15)
        try:
            pred = model.predict(
                c,
                v,
                threshold_method=threshold_method,  # type: ignore[arg-type]
                percentile=percentile,
                k=k,
            )
        except Exception:
            # 模型状态异常时自动回退重训练一次，避免缓存污染导致接口不可用。
            self.train_anomaly_model(model_name, coords, values, epochs=15)
            model = self._get_or_train_anomaly_model(model_name, coords, values, epochs=15)
            pred = model.predict(
                c,
                v,
                threshold_method=threshold_method,  # type: ignore[arg-type]
                percentile=percentile,
                k=k,
            )
        normalized_pred = dict(pred)
        if "anomaly_scores" not in normalized_pred:
            if "scores" in normalized_pred:
                normalized_pred["anomaly_scores"] = normalized_pred.get("scores", [])
            elif "node_scores" in normalized_pred:
                normalized_pred["anomaly_scores"] = normalized_pred.get("node_scores", [])
        count = float(pred.get("anomaly_count", len(pred.get("anomaly_indices", []))))
        self.metric_monitor.log(f"{model_name}_anomaly_count", count)

        scores = pred.get("scores", pred.get("node_scores", []))
        result = {
            "model_name": model_name,
            "prediction": normalized_pred,
            "resource": self.resource_monitor.collect(),
            "score_preview": list(scores[:10]),
        }
        self.anomaly_cache.set("prediction", predict_cache_key, result)
        self.metric_monitor.log(f"{model_name}_prediction_cache_hit", 0.0)
        return self._with_cache_meta(result, namespace="prediction", cache_hit=False)

    def detect_realtime_anomaly(
        self,
        model_name: str,
        stream_batches: list[dict[str, Any]],
        threshold_method: str = "adaptive",
        percentile: float = 95.0,
        k: float = 2.5,
    ) -> dict[str, Any]:
        responses: list[dict[str, Any]] = []
        for i, batch in enumerate(stream_batches):
            coords = batch.get("coords", [])
            values = batch.get("values", [])
            pred = self.predict_anomaly(
                model_name=model_name,
                coords=coords,
                values=values,
                threshold_method=threshold_method,
                percentile=percentile,
                k=k,
            )
            responses.append({"batch_index": i, "result": pred})
        return {"model_name": model_name, "batches": responses}

    def explain_anomaly(
        self,
        *,
        model_name: str,
        coords: list[list[float]],
        values: list[float],
        method: str = "hybrid",
        top_k: int = 5,
        include_prediction: bool = True,
        num_samples: int | None = None,
        nsamples: int | None = None,
        max_explain_nodes: int = 8,
    ) -> dict[str, Any]:
        if model_name not in {"vae", "gcae", "gan", "contrastive"}:
            raise ValueError("model_name must be one of vae/gcae/gan/contrastive")
        if method not in {"lime", "shap", "hybrid"}:
            raise ValueError("method must be one of lime/shap/hybrid")

        c, v = self._validate_coords_values(coords, values)
        model = self._get_or_train_anomaly_model(model_name, coords, values, epochs=15)
        model_version = self._model_version(model_name)
        explain_cache_key = self._explanation_cache_key(
            model_name=model_name,
            model_version=model_version,
            coords=c,
            values=v,
            method=method,
            top_k=top_k,
            include_prediction=include_prediction,
            num_samples=num_samples,
            nsamples=nsamples,
            max_explain_nodes=max_explain_nodes,
        )
        cached_explanation = self.anomaly_cache.get("explanation", explain_cache_key)
        if cached_explanation is not None:
            self.metric_monitor.log(f"{model_name}_explain_cache_hit", 1.0)
            return self._with_cache_meta(cached_explanation, namespace="explanation", cache_hit=True)

        feature_analysis = self.anomaly_feature_registry.analyze(model_name)

        lime_adapter: Any | None = None
        shap_adapter: Any | None = None
        if model_name == "vae":
            lime_adapter = self.vae_lime_adapter
            shap_adapter = self.vae_shap_adapter
        elif model_name == "gcae":
            lime_adapter = self.gcae_lime_adapter
            shap_adapter = self.gcae_shap_adapter
        elif model_name == "gan":
            lime_adapter = self.gan_lime_adapter
            shap_adapter = self.gan_shap_adapter
        elif model_name == "contrastive":
            lime_adapter = self.contrastive_lime_adapter
            shap_adapter = self.contrastive_shap_adapter

        if method in {"lime", "hybrid"} and lime_adapter is None:
            pending_payload = {
                "model_name": model_name,
                "summary": {
                    "method": method,
                    "adapter_status": "pending",
                    "message": "当前模型尚未实现 LIME 解释适配器。",
                },
                "feature_analysis": feature_analysis,
            }
            self.anomaly_cache.set("explanation", explain_cache_key, pending_payload)
            self.metric_monitor.log(f"{model_name}_explain_cache_hit", 0.0)
            return self._with_cache_meta(pending_payload, namespace="explanation", cache_hit=False)
        if method in {"shap", "hybrid"} and shap_adapter is None:
            pending_payload = {
                "model_name": model_name,
                "summary": {
                    "method": method,
                    "adapter_status": "pending",
                    "message": "当前模型尚未实现 SHAP 解释适配器。",
                },
                "feature_analysis": feature_analysis,
            }
            self.anomaly_cache.set("explanation", explain_cache_key, pending_payload)
            self.metric_monitor.log(f"{model_name}_explain_cache_hit", 0.0)
            return self._with_cache_meta(pending_payload, namespace="explanation", cache_hit=False)

        lime_result: dict[str, Any] | None = None
        if method in {"lime", "hybrid"}:
            lime_result = lime_adapter.explain(
                model=model,
                coords=c,
                values=v,
                top_k=top_k,
                num_samples=num_samples,
                max_explain_nodes=max_explain_nodes,
            )

        shap_result: dict[str, Any] | None = None
        if method in {"shap", "hybrid"}:
            shap_result = shap_adapter.explain(
                model=model,
                coords=c,
                values=v,
                top_k=top_k,
                nsamples=nsamples,
                max_explain_nodes=max_explain_nodes,
            )

        top_features: list[dict[str, Any]] = []
        if method == "lime" and lime_result is not None:
            top_features = list(lime_result.get("summary", {}).get("top_features", []))
        elif method == "shap" and shap_result is not None:
            top_features = list(shap_result.get("summary", {}).get("top_features", []))
        elif method == "hybrid":
            if shap_result is not None:
                top_features = list(shap_result.get("summary", {}).get("top_features", []))
            if not top_features and lime_result is not None:
                top_features = list(lime_result.get("summary", {}).get("top_features", []))

        result: dict[str, Any] = {
            "model_name": model_name,
            "summary": {
                "method": method,
                "top_features": top_features,
                "max_explain_nodes": int(max_explain_nodes),
                "feature_count": int(feature_analysis["feature_count"]),
            },
            "feature_analysis": feature_analysis,
        }
        if lime_result is not None:
            result["lime"] = lime_result
        if shap_result is not None:
            result["shap"] = shap_result
        if include_prediction:
            try:
                pred = model.predict(c, v, threshold_method="percentile", percentile=95.0, k=2.5)
            except Exception:
                self.train_anomaly_model(model_name, coords, values, epochs=15)
                model = self._get_or_train_anomaly_model(model_name, coords, values, epochs=15)
                pred = model.predict(c, v, threshold_method="percentile", percentile=95.0, k=2.5)
            result["prediction"] = pred
        self.anomaly_cache.set("explanation", explain_cache_key, result)
        self.metric_monitor.log(f"{model_name}_explain_cache_hit", 0.0)
        return self._with_cache_meta(result, namespace="explanation", cache_hit=False)

    def anomaly_cache_metrics(self) -> dict[str, Any]:
        return self.anomaly_cache.stats()

    def cleanup_anomaly_cache(self, namespace: str | None = None) -> dict[str, Any]:
        removed = self.anomaly_cache.cleanup(namespace=namespace)
        return {"removed": removed, "stats": self.anomaly_cache.stats()}

    def invalidate_anomaly_cache(
        self,
        *,
        namespace: str | None = None,
        model_name: str | None = None,
        model_version: int | None = None,
        key_prefix: str | None = None,
    ) -> dict[str, Any]:
        if model_name and namespace is None and key_prefix is None:
            if model_version is None:
                pred_prefix = f"prediction:{model_name}:"
                exp_prefix = f"explanation:{model_name}:"
            else:
                pred_prefix = self._cache_prefix("prediction", model_name, int(model_version))
                exp_prefix = self._cache_prefix("explanation", model_name, int(model_version))
            removed_pred = self.anomaly_cache.invalidate(namespace="prediction", key_prefix=pred_prefix)
            removed_exp = self.anomaly_cache.invalidate(namespace="explanation", key_prefix=exp_prefix)
            removed = {
                "prediction": int(removed_pred.get("prediction", 0)),
                "explanation": int(removed_exp.get("explanation", 0)),
            }
            return {"removed": removed, "stats": self.anomaly_cache.stats(), "key_prefix": f"{pred_prefix}|{exp_prefix}"}

        prefix = key_prefix
        if prefix is None and model_name:
            if model_version is None:
                prefix = f"{namespace}:{model_name}:"
            else:
                prefix = self._cache_prefix(namespace or "prediction", model_name, int(model_version))
        removed = self.anomaly_cache.invalidate(namespace=namespace, key_prefix=prefix)
        return {"removed": removed, "stats": self.anomaly_cache.stats(), "key_prefix": prefix}

    def warmup_anomaly_cache(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        summary = self.anomaly_cache.warmup(items)
        return {"warmup": summary, "stats": self.anomaly_cache.stats()}

    def persist_anomaly_cache(self) -> dict[str, Any]:
        return self.anomaly_cache.persist()

    def clear_anomaly_cache(self, namespace: str | None = None) -> dict[str, Any]:
        removed = self.anomaly_cache.clear(namespace=namespace)
        return {"removed": removed, "stats": self.anomaly_cache.stats()}

    def train_spatial_model(self, model_type: str, samples: list[list[float]], epochs: int = 30) -> dict[str, Any]:
        coords, values = self._to_spatial_arrays(samples)
        targets = values.copy()

        if model_type not in {"gnn", "attention", "residual"}:
            raise ValueError("model_type must be one of gnn/attention/residual")

        if model_type == "gnn":
            model = self.registry.create("gnn_kriging")
        elif model_type == "attention":
            model = self.registry.create("attention_kriging")
        else:
            model = self.registry.create("residual_kriging")

        dataset = [{"coords": coords, "values": values, "targets": targets} for _ in range(6)]
        train_set = dataset[:4]
        val_set = dataset[4:]

        result = train_spatial_model(
            model,
            train_dataset=train_set,
            val_dataset=val_set,
            config=SpatialTrainingConfig(max_epochs=max(5, epochs), learning_rate=0.03, early_stopping_patience=5),
        )

        self.metric_monitor.log(f"{model_type}_val_loss", float(result["training"]["best_val_loss"]))
        return {
            "model_type": model_type,
            "training": result["training"],
            "history": result["history"],
        }

    def predict_spatial(
        self,
        model_type: str,
        samples: list[list[float]],
        queries: list[list[float]],
        blend_ratio: float = 0.6,
    ) -> dict[str, Any]:
        coords, values = self._to_spatial_arrays(samples)
        query_coords = np.asarray(queries, dtype=float)
        if query_coords.ndim != 2 or query_coords.shape[1] != 2:
            raise ValueError("queries must be [[x, y], ...]")

        model_map = {
            "gnn": "gnn",
            "attention": "attention",
            "residual": "residual",
        }
        if model_type not in model_map:
            raise ValueError("model_type must be one of gnn/attention/residual")

        fused = self.integrator.predict_with_fusion(
            sample_coords=coords,
            sample_values=values,
            query_coords=query_coords,
            model_type=model_map[model_type],
            blend_ratio=blend_ratio,
        )

        self.metric_monitor.log("spatial_inference_count", float(len(query_coords)))
        return {
            "model_type": model_type,
            "prediction": fused.mean.tolist(),
            "variance": fused.variance.tolist(),
            "source": fused.source,
            "resource": self.resource_monitor.collect(),
        }

    def train_spatiotemporal_model(
        self,
        model_type: str,
        coords: list[list[float]],
        series: list[list[list[float]]],
        targets: list[list[float]] | None = None,
        epochs: int = 20,
        pred_horizon: int = 6,
    ) -> dict[str, Any]:
        if model_type not in {"st_transformer", "gcn_lstm", "convlstm", "stgcn"}:
            raise ValueError("model_type must be one of st_transformer/gcn_lstm/convlstm/stgcn")

        c, s, horizon = self._validate_spatiotemporal_inputs(coords, series, pred_horizon)
        if targets is None:
            if s.shape[1] <= horizon + 2:
                raise ValueError("series length must be greater than pred_horizon when targets are omitted")
            y = s[:, -horizon:, 0]
            x = s[:, :-horizon, :]
        else:
            y = np.asarray(targets, dtype=float)
            if y.ndim != 2:
                raise ValueError("targets must be [n_nodes, pred_horizon]")
            if y.shape[0] != c.shape[0]:
                raise ValueError("targets node count mismatch")
            if y.shape[1] != horizon:
                raise ValueError("targets horizon mismatch")
            x = s

        sample = {
            "coords": c,
            "series": x,
            "targets": y,
            "adjacency": np.ones((len(c), len(c)), dtype=float) - np.eye(len(c), dtype=float),
        }
        dataset = [sample for _ in range(8)]
        train_set = dataset[:6]
        val_set = dataset[6:]

        result = self.spatiotemporal_integrator.train(
            model_type=model_type,  # type: ignore[arg-type]
            train_dataset=train_set,
            val_dataset=val_set,
            config=SpatioTemporalTrainingConfig(
                seq_len=int(x.shape[1]),
                pred_horizon=horizon,
                max_epochs=max(5, int(epochs)),
                learning_rate=0.02,
                warmup_epochs=3,
                early_stopping_patience=5,
                gradient_clip_norm=1.0,
            ),
        )
        perf = self.spatiotemporal_integrator.performance_benchmark(
            model_type=model_type,  # type: ignore[arg-type]
            coords=c,
            series=x,
            pred_horizon=horizon,
            repeat=3,
        )
        self.metric_monitor.log(f"{model_type}_st_val_loss", float(result["training"]["best_val_loss"]))
        return {
            "model_type": model_type,
            "training": result["training"],
            "history": result["history"],
            "monitor": result["monitor"],
            "performance": perf,
        }

    def predict_spatiotemporal(
        self,
        model_type: str,
        coords: list[list[float]],
        series: list[list[list[float]]],
        pred_horizon: int = 6,
        fusion_strategy: str = "gating",
        targets: list[list[float]] | None = None,
        blend_ratio: float = 0.7,
        uncertainty_method: str | None = None,
        enable_memory_optimization: bool = False,
        enable_gpu_acceleration: bool = False,
        enable_inference_acceleration: bool = True,
        enable_long_sequence_optimization: bool = False,
        long_sequence_chunk: int = 48,
    ) -> dict[str, Any]:
        if model_type not in {"st_transformer", "gcn_lstm", "convlstm", "stgcn"}:
            raise ValueError("model_type must be one of st_transformer/gcn_lstm/convlstm/stgcn")
        c, s, horizon = self._validate_spatiotemporal_inputs(coords, series, pred_horizon)

        pred = self.spatiotemporal_integrator.predict(
            model_type=model_type,  # type: ignore[arg-type]
            coords=c,
            series=s,
            pred_horizon=horizon,
            fusion_strategy=fusion_strategy,
            blend_ratio=float(blend_ratio),
            uncertainty_method=uncertainty_method,
            enable_memory_optimization=bool(enable_memory_optimization),
            enable_gpu_acceleration=bool(enable_gpu_acceleration),
            enable_inference_acceleration=bool(enable_inference_acceleration),
            enable_long_sequence_optimization=bool(enable_long_sequence_optimization),
            long_sequence_chunk=max(8, int(long_sequence_chunk)),
        )

        baseline = self.spatiotemporal_integrator.baseline_predictions(s, pred_horizon=horizon)
        evaluation = None
        if targets is not None:
            y = np.asarray(targets, dtype=float)
            if y.shape == pred.mean.shape:
                evaluation = self.spatiotemporal_integrator.evaluate(
                    y_true=y,
                    y_pred=pred.mean,
                    y_var=pred.variance,
                    coords=c,
                    baseline_preds=baseline,
                )

        analysis = self.spatiotemporal_integrator.analyze_time_series(s)
        self.metric_monitor.log(f"{model_type}_st_inference_count", float(len(c)))
        return {
            "model_type": model_type,
            "prediction": pred.mean.tolist(),
            "variance": pred.variance.tolist(),
            "source": pred.source,
            "uncertainty_method": pred.uncertainty_method,
            "optimization": pred.optimization,
            "evaluation": evaluation,
            "analysis": {
                "adf": analysis["adf"],
                "kpss": analysis["kpss"],
                "temporal_anomaly_count": int(len(analysis["temporal_anomaly"]["indices"])),
            },
            "baseline": {
                "naive": baseline["naive"].tolist(),
                "arima_proxy": baseline["arima_proxy"].tolist(),
                "lstm_proxy": baseline["lstm_proxy"].tolist(),
            },
            "resource": self.resource_monitor.collect(),
        }

    def update_spatiotemporal_online(
        self,
        model_type: str,
        coords: list[list[float]],
        long_series: list[list[list[float]]],
        window_size: int = 24,
        pred_horizon: int = 6,
        update_interval: int = 1,
        strategy: str = "standard",
    ) -> dict[str, Any]:
        if model_type not in {"st_transformer", "gcn_lstm", "convlstm", "stgcn"}:
            raise ValueError("model_type must be one of st_transformer/gcn_lstm/convlstm/stgcn")
        c, s, horizon = self._validate_spatiotemporal_inputs(coords, long_series, pred_horizon)

        payload = self.spatiotemporal_integrator.realtime_predict_and_update(
            model_type=model_type,  # type: ignore[arg-type]
            coords=c,
            long_series=s,
            window_size=max(4, int(window_size)),
            pred_horizon=horizon,
            update_interval=max(1, int(update_interval)),
            strategy=strategy,
        )
        self.metric_monitor.log(f"{model_type}_st_online_updates", float(payload["online_update"]["updated_steps"]))
        return {
            "model_type": model_type,
            "online": payload,
            "resource": self.resource_monitor.collect(),
        }

    def warmup_spatiotemporal_model(self, model_type: str = "st_transformer") -> dict[str, Any]:
        if model_type not in {"st_transformer", "gcn_lstm", "convlstm", "stgcn"}:
            raise ValueError("model_type must be one of st_transformer/gcn_lstm/convlstm/stgcn")

        cache = self._spatiotemporal_model_cache.get(model_type)
        now_ts = time.time()
        if cache:
            cache["last_access_ts"] = now_ts
            return {"model_type": model_type, "warmed": True, "from_cache": True}

        # 使用最小规模数据触发一次轻量预测路径，达到模型预热效果。
        coords = np.array([[0.0, 0.0], [1.0, 0.5], [0.5, 1.0], [1.5, 1.2]], dtype=float)
        seq_len = 12
        series = np.tile(np.linspace(0.1, 1.2, seq_len, dtype=float), (coords.shape[0], 1)).reshape(coords.shape[0], seq_len, 1)
        _ = self.spatiotemporal_integrator.predict(
            model_type=model_type,  # type: ignore[arg-type]
            coords=coords,
            series=series,
            pred_horizon=3,
            fusion_strategy="gating",
            blend_ratio=0.7,
            enable_inference_acceleration=True,
        )
        self._spatiotemporal_model_cache[model_type] = {
            "model_type": model_type,
            "last_access_ts": now_ts,
            "warmup_seq_len": seq_len,
        }
        return {"model_type": model_type, "warmed": True, "from_cache": False}

    def _predict_spatiotemporal_batched(
        self,
        *,
        model_type: str,
        coords: np.ndarray,
        series: np.ndarray,
        pred_horizon: int,
        batch_size: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        n_nodes = int(coords.shape[0])
        if n_nodes <= batch_size:
            pred = self.spatiotemporal_integrator.predict(
                model_type=model_type,  # type: ignore[arg-type]
                coords=coords,
                series=series,
                pred_horizon=pred_horizon,
                fusion_strategy="gating",
                blend_ratio=0.7,
                enable_inference_acceleration=True,
            )
            return pred.mean, pred.variance

        all_mean: list[np.ndarray] = []
        all_var: list[np.ndarray] = []
        chunks = [(start, min(n_nodes, start + batch_size)) for start in range(0, n_nodes, batch_size)]
        tasks = [
            ParallelTask(
                task_id=f"batch-{start}-{end}",
                priority=int(rank),
                payload={"start": int(start), "end": int(end)},
            )
            for rank, (start, end) in enumerate(chunks)
        ]

        outputs, _ = self.batch_parallel.run_tasks(
            tasks=tasks,
            task_type="cpu",
            worker_fn=lambda payload: (
                int(payload["start"]),
                self.spatiotemporal_integrator.predict(
                    model_type=model_type,  # type: ignore[arg-type]
                    coords=coords[int(payload["start"]): int(payload["end"])],
                    series=series[int(payload["start"]): int(payload["end"])],
                    pred_horizon=pred_horizon,
                    fusion_strategy="gating",
                    blend_ratio=0.7,
                    enable_inference_acceleration=True,
                ),
            )
        )
        outputs.sort(key=lambda item: item[0])
        for _, pred in outputs:
            all_mean.append(pred.mean)
            all_var.append(pred.variance)
        return np.vstack(all_mean), np.vstack(all_var)

    def explain_spatiotemporal(
        self,
        *,
        model_type: str,
        coords: list[list[float]],
        series: list[list[list[float]]],
        pred_horizon: int = 6,
        method: str = "hybrid",
        top_k: int = 5,
        include_prediction: bool = True,
        batch_size: int = 256,
    ) -> dict[str, Any]:
        if model_type not in {"st_transformer", "gcn_lstm", "convlstm", "stgcn"}:
            raise ValueError("model_type must be one of st_transformer/gcn_lstm/convlstm/stgcn")
        if method not in {"lime", "shap", "hybrid"}:
            raise ValueError("method must be one of lime/shap/hybrid")

        c, s, horizon = self._validate_spatiotemporal_inputs(coords, series, pred_horizon)
        batch = max(16, int(batch_size))
        self.warmup_spatiotemporal_model(model_type=model_type)
        pred_mean, pred_var = self._predict_spatiotemporal_batched(
            model_type=model_type,
            coords=c,
            series=s,
            pred_horizon=horizon,
            batch_size=batch,
        )

        baseline = np.mean(s, axis=1, keepdims=True)
        node_feature_importance = np.mean(np.abs(s - baseline), axis=1)
        heuristic_feature_importance = np.mean(node_feature_importance, axis=0)
        temporal_diff = np.abs(np.diff(s[:, :, 0], axis=1))
        temporal_importance = np.mean(temporal_diff, axis=0) if temporal_diff.size else np.array([], dtype=float)
        center = np.mean(c, axis=0, keepdims=True)
        spatial_distance = np.linalg.norm(c - center, axis=1)
        spatial_importance = (spatial_distance / (np.max(spatial_distance) + 1e-6)).astype(float)

        lime_result: dict[str, Any] | None = None
        if method in {"lime", "hybrid"}:
            lime_result = self.lime_explainer.explain(
                model_type=model_type,
                coords=c,
                series=s,
                pred_mean=pred_mean,
                top_k=top_k,
            )
        shap_result: dict[str, Any] | None = None
        if method in {"shap", "hybrid"}:
            shap_result = self.shap_explainer.explain(
                model_type=model_type,
                coords=c,
                series=s,
                pred_mean=pred_mean,
                top_k=top_k,
            )

        feature_importance = heuristic_feature_importance.copy()
        top_features: list[dict[str, Any]] = []
        if method == "lime" and lime_result is not None:
            lime_importance = np.asarray(lime_result.get("feature_importance", []), dtype=float)
            if lime_importance.size == feature_importance.size:
                feature_importance = lime_importance
            top_features = list(lime_result.get("summary", {}).get("top_features", []))
        elif method == "shap" and shap_result is not None:
            shap_importance = np.asarray(shap_result.get("feature_importance", []), dtype=float)
            if shap_importance.size == feature_importance.size:
                feature_importance = shap_importance
            top_features = list(shap_result.get("summary", {}).get("top_features", []))
        elif method == "hybrid" and lime_result is not None:
            parts: list[np.ndarray] = [heuristic_feature_importance]
            lime_importance = np.asarray(lime_result.get("feature_importance", []), dtype=float)
            if lime_importance.size == feature_importance.size:
                parts.append(lime_importance)
            if shap_result is not None:
                shap_importance = np.asarray(shap_result.get("feature_importance", []), dtype=float)
                if shap_importance.size == feature_importance.size:
                    parts.append(shap_importance)
            feature_importance = np.mean(np.vstack(parts), axis=0)
            if shap_result is not None:
                top_features = list(shap_result.get("summary", {}).get("top_features", []))
            if not top_features:
                top_features = list(lime_result.get("summary", {}).get("top_features", []))
        if not top_features:
            k = max(1, min(int(top_k), int(feature_importance.shape[0])))
            top_feature_idx = np.argsort(-feature_importance)[:k]
            top_features = [
                {"feature_index": int(idx), "importance": float(feature_importance[idx])}
                for idx in top_feature_idx
            ]

        summary = {
            "method": method,
            "n_nodes": int(c.shape[0]),
            "seq_len": int(s.shape[1]),
            "n_features": int(s.shape[2]),
            "pred_horizon": int(horizon),
            "top_features": top_features,
            "spatial_importance_mean": float(np.mean(spatial_importance)),
            "temporal_importance_mean": float(np.mean(temporal_importance)) if temporal_importance.size else 0.0,
        }
        if lime_result is not None:
            summary["lime_average_confidence"] = float(lime_result.get("summary", {}).get("average_confidence", 0.0))
            summary["lime_num_samples"] = int(lime_result.get("summary", {}).get("num_samples", 0))
        if shap_result is not None:
            summary["shap_average_confidence"] = float(shap_result.get("summary", {}).get("average_confidence", 0.0))
            summary["shap_background_size"] = int(shap_result.get("summary", {}).get("background_size", 0))

        result: dict[str, Any] = {
            "model_type": model_type,
            "summary": summary,
            "feature_importance": feature_importance.astype(float).tolist(),
            "node_importance": np.mean(node_feature_importance, axis=1).astype(float).tolist(),
            "spatial_importance": spatial_importance.tolist(),
            "temporal_importance": temporal_importance.astype(float).tolist(),
        }
        if lime_result is not None:
            result["lime"] = {
                "batch_explanations": lime_result.get("batch_explanations", []),
                "global_feature_importance": lime_result.get("global_feature_importance", []),
                "visualization": lime_result.get("visualization", {}),
                "performance": lime_result.get("performance", {}),
            }
        if shap_result is not None:
            result["shap"] = {
                "batch_explanations": shap_result.get("batch_explanations", []),
                "global_feature_importance": shap_result.get("global_feature_importance", []),
                "interaction_values": shap_result.get("interaction_values", []),
                "visualization": shap_result.get("visualization", {}),
                "performance": shap_result.get("performance", {}),
            }
        if include_prediction:
            result["prediction"] = pred_mean.tolist()
            result["variance"] = pred_var.tolist()
        result["parallel"] = {
            "batch_monitor": self.batch_parallel.snapshot(),
            "lime_monitor": self.lime_explainer._parallel.snapshot(),
            "shap_monitor": self.shap_explainer._parallel.snapshot(),
        }
        return result

    def train_fusion_profile(
        self,
        profile_id: str,
        models: list[dict[str, Any]],
        true_values: list[float],
        strategy: str = "dynamic",
        weight_method: str = "adaptive",
        adaptive_mode: str = "neural",
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        result = self.fusion_platform.train_fusion_profile(
            profile_id=profile_id,
            models=models,
            true_values=true_values,
            strategy=strategy,
            weight_method=weight_method,
            adaptive_mode=adaptive_mode,
            context=context,
        )
        rmse = float(result["result"]["metrics"].get("rmse", 0.0)) if result.get("result") else 0.0
        self.metric_monitor.log("fusion_profile_train_rmse", rmse)
        return result

    def predict_fusion(
        self,
        models: list[dict[str, Any]],
        profile_id: str | None = None,
        strategy: str | None = None,
        weight_method: str | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        payload = self.fusion_platform.inference(
            models=models,
            profile_id=profile_id,
            strategy=strategy,
            weight_method=weight_method,
            true_values=true_values,
            context=context,
        )
        self.metric_monitor.log("fusion_inference_count", float(len(models)))
        return payload

    def compare_fusion_strategies(
        self,
        models: list[dict[str, Any]],
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        return self.fusion_platform.compare_strategies(
            models=models,
            true_values=true_values,
            context=context,
        )

    def optimize_fusion_weights(
        self,
        models: list[dict[str, Any]],
        true_values: list[float],
        strategy: str = "weighted_average",
    ) -> dict[str, Any]:
        return self.fusion_platform.optimize_weights(
            models=models,
            true_values=true_values,
            strategy=strategy,
        )

    def hybrid_fusion(
        self,
        kriging_prediction: list[float],
        deep_prediction: list[float],
        mode: str = "residual",
        ratio: float = 0.6,
        kriging_variance: list[float] | None = None,
        deep_variance: list[float] | None = None,
    ) -> dict[str, Any]:
        return self.fusion_platform.hybrid_fusion(
            kriging_prediction=kriging_prediction,
            deep_prediction=deep_prediction,
            mode=mode,
            ratio=ratio,
            kriging_variance=kriging_variance,
            deep_variance=deep_variance,
        )

    def multimodal_fusion(
        self,
        modalities: list[list[float]],
        strategy: str = "hybrid",
        weights: list[float] | None = None,
    ) -> dict[str, Any]:
        return self.fusion_platform.multimodal_fusion(
            modalities=modalities,
            strategy=strategy,
            weights=weights,
        )

    def select_fusion_model(
        self,
        performance_scores: dict[str, float] | None = None,
        uncertainty_scores: dict[str, float] | None = None,
        input_score: float | None = None,
    ) -> dict[str, Any]:
        return self.fusion_platform.select_model(
            performance_scores=performance_scores,
            uncertainty_scores=uncertainty_scores,
            input_score=input_score,
        )

    def fusion_monitor_status(self) -> dict[str, Any]:
        return self.fusion_platform.monitor_status()

    def fusion_registry_status(self) -> dict[str, Any]:
        return self.fusion_platform.model_registry_status()

    def fusion_check_access(self, token: str | None, client_id: str = "anonymous") -> dict[str, Any]:
        return self.fusion_platform.check_access(token=token, client_id=client_id)
