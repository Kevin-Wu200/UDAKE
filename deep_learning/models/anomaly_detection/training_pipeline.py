"""异常检测训练配置、优化、模型选择与持久化。"""

from __future__ import annotations

import pickle
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from .contrastive_anomaly import ContrastiveAnomalyDetector
from .gan_anomaly import GANAnomalyDetector
from .gcae_anomaly import GCAEAnomalyDetector
from .vae_anomaly import VAEAnomalyDetector

ModelName = Literal["vae", "gcae", "gan", "contrastive"]


@dataclass
class AnomalyTrainingConfig:
    model_name: ModelName
    max_epochs: int = 30
    threshold_method: str = "percentile"
    threshold_percentile: float = 95.0
    learning_rate: float = 1e-3
    batch_size: int = 64


class TrainingMonitor:
    """训练监控器。"""

    def __init__(self) -> None:
        self.records: list[dict[str, float]] = []

    def log(self, **kwargs: float) -> None:
        payload = {k: float(v) for k, v in kwargs.items()}
        self.records.append(payload)

    def latest(self) -> dict[str, float]:
        return self.records[-1] if self.records else {}


class HyperparameterOptimizer:
    """网格搜索超参数优化器。"""

    def optimize(
        self,
        builder: Any,
        coords: np.ndarray,
        values: np.ndarray,
        param_grid: dict[str, list[Any]],
        score_fn: Any,
    ) -> dict[str, Any]:
        keys = list(param_grid.keys())
        if not keys:
            model = builder()
            train_info = model.fit(coords, values)
            score = float(score_fn(model))
            return {"best_score": score, "best_params": {}, "train_info": train_info}

        best_score = -float("inf")
        best_params: dict[str, Any] = {}
        best_train_info: dict[str, Any] = {}

        def dfs(index: int, current: dict[str, Any]) -> None:
            nonlocal best_score, best_params, best_train_info
            if index >= len(keys):
                model = builder(**current)
                train_info = model.fit(coords, values)
                score = float(score_fn(model))
                if score > best_score:
                    best_score = score
                    best_params = dict(current)
                    best_train_info = train_info
                return
            key = keys[index]
            for value in param_grid[key]:
                current[key] = value
                dfs(index + 1, current)

        dfs(0, {})
        return {"best_score": best_score, "best_params": best_params, "train_info": best_train_info}


class ModelSelector:
    """基于评估指标选择最佳模型。"""

    def select(self, candidates: dict[str, dict[str, float]], key: str = "f1") -> tuple[str, dict[str, float]]:
        if not candidates:
            raise ValueError("候选模型为空")
        ranked = sorted(candidates.items(), key=lambda item: item[1].get(key, -float("inf")), reverse=True)
        return ranked[0][0], ranked[0][1]


class ModelStore:
    """模型保存和加载。"""

    def save(self, model: Any, path: str) -> str:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as fp:
            pickle.dump(model, fp)
        return str(output)

    def load(self, path: str) -> Any:
        with Path(path).open("rb") as fp:
            return pickle.load(fp)


class AnomalyTrainingManager:
    """统一训练入口。"""

    def __init__(self) -> None:
        self.monitor = TrainingMonitor()
        self.optimizer = HyperparameterOptimizer()
        self.selector = ModelSelector()
        self.store = ModelStore()

    def build_model(self, model_name: ModelName) -> Any:
        if model_name == "vae":
            return VAEAnomalyDetector()
        if model_name == "gcae":
            return GCAEAnomalyDetector()
        if model_name == "gan":
            return GANAnomalyDetector()
        if model_name == "contrastive":
            return ContrastiveAnomalyDetector()
        raise ValueError(f"不支持的模型: {model_name}")

    def train(self, config: AnomalyTrainingConfig, coords: np.ndarray, values: np.ndarray) -> dict[str, Any]:
        model = self.build_model(config.model_name)
        if config.model_name == "contrastive":
            result = model.fit(coords, values, epochs=config.max_epochs)
        else:
            # 与统一配置对齐：最大轮数由配置控制。
            if hasattr(model, "config") and hasattr(model.config, "max_epochs"):
                model.config.max_epochs = int(max(1, config.max_epochs))
            result = model.fit(coords, values)

        self.monitor.log(train_loss=result.get("best_total_loss", result.get("final_loss", 0.0)))
        return {
            "model": model,
            "training": result,
            "config": asdict(config),
        }

    def tune(
        self,
        model_name: ModelName,
        coords: np.ndarray,
        values: np.ndarray,
        param_grid: dict[str, list[Any]],
        score_fn: Any,
    ) -> dict[str, Any]:
        builders = {
            "vae": lambda **kwargs: VAEAnomalyDetector(),
            "gcae": lambda **kwargs: GCAEAnomalyDetector(),
            "gan": lambda **kwargs: GANAnomalyDetector(),
            "contrastive": lambda **kwargs: ContrastiveAnomalyDetector(),
        }
        if model_name not in builders:
            raise ValueError(f"不支持的模型: {model_name}")

        return self.optimizer.optimize(builders[model_name], coords, values, param_grid, score_fn)
