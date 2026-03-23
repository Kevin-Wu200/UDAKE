"""深度学习服务编排层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ai_extension.异常检测模块 import DeepAnomalyFusionDetector
from deep_learning.inference import BatchPredictor
from deep_learning.models.anomaly_detection import AnomalyTrainingConfig, AnomalyTrainingManager
from deep_learning.models import AttentionKrigingModel, GNNKrigingModel, ModelRegistry, ResidualKrigingModel
from deep_learning.models.spatial_interpolation import SpatialInterpolationIntegrator
from deep_learning.training import LightningTrainer, SpatialTrainingConfig, TrainingConfig, train_spatial_model
from deep_learning.utils.device import DeviceManager
from deep_learning.utils.monitoring import AlertManager, AlertRule, MetricMonitor, SystemResourceMonitor


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

    def health(self) -> dict[str, Any]:
        profile = self.device_manager.configure()
        return {
            "status": "healthy",
            "device": profile.device,
            "cuda_available": profile.cuda_available,
            "mps_available": profile.mps_available,
            "registered_models": self.registry.list_models(),
            "trained_anomaly_models": sorted(self.anomaly_models.keys()),
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

        if model_name == "fusion":
            x = c[:, 0]
            y = c[:, 1]
            result = self.deep_fusion.detect(x, y, v, threshold_method=threshold_method, percentile=percentile)
            self.metric_monitor.log("fusion_anomaly_count", float(result["anomaly_count"]))
            return result

        if model_name not in self.anomaly_models:
            self.train_anomaly_model(model_name, coords, values, epochs=15)
        model = self.anomaly_models[model_name]

        pred = model.predict(
            c,
            v,
            threshold_method=threshold_method,  # type: ignore[arg-type]
            percentile=percentile,
            k=k,
        )
        count = float(pred.get("anomaly_count", len(pred.get("anomaly_indices", []))))
        self.metric_monitor.log(f"{model_name}_anomaly_count", count)

        scores = pred.get("scores", pred.get("node_scores", []))
        return {
            "model_name": model_name,
            "prediction": pred,
            "resource": self.resource_monitor.collect(),
            "score_preview": list(scores[:10]),
        }

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
