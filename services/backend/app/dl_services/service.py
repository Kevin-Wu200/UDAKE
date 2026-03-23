"""深度学习服务编排层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deep_learning.inference import BatchPredictor
from deep_learning.training import LightningTrainer, TrainingConfig
from deep_learning.utils.device import DeviceManager
from deep_learning.utils.monitoring import AlertManager, AlertRule, MetricMonitor, SystemResourceMonitor
from deep_learning.models import ModelRegistry


@dataclass
class DummyRegressor:
    """用于基础架构验证的轻量模型。"""

    bias: float = 0.0

    def train_step(self, batch: list[list[float]], lr: float = 0.01, mixed_precision: bool = False) -> float:
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
        self.metric_monitor = MetricMonitor()
        self.resource_monitor = SystemResourceMonitor()
        self.alert_manager = AlertManager([AlertRule(metric="val_loss", threshold=1.0, operator=">=")])
        self.device_manager = DeviceManager()

    def health(self) -> dict[str, Any]:
        profile = self.device_manager.configure()
        return {
            "status": "healthy",
            "device": profile.device,
            "cuda_available": profile.cuda_available,
            "mps_available": profile.mps_available,
            "registered_models": self.registry.list_models(),
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
