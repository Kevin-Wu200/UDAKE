"""不确定性模型训练配置、选择与持久化。"""

from __future__ import annotations

import pickle
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from .bnn import BayesianNeuralRegressor, GaussianMixturePrior, GaussianPrior
from .deep_ensemble import DeepEnsembleRegressor
from .edl import EDLClassifier, EDLConfig
from .mc_dropout import MCDropoutConfig, MCDropoutRegressor

UQModelName = Literal["bnn", "mc_dropout", "deep_ensemble", "edl"]


@dataclass
class UQTrainingConfig:
    model_name: UQModelName
    max_epochs: int = 200
    learning_rate: float = 8e-3
    uncertainty_weight: float = 0.4
    regularization: float = 0.05
    optimizer: str = "adam_like"
    hidden_dim: int = 32
    num_classes: int = 3


class UQTrainingMonitor:
    def __init__(self) -> None:
        self.loss_curve: list[float] = []
        self.uncertainty_curve: list[float] = []
        self.calibration_curve: list[float] = []

    def log(self, loss: float, uncertainty: float = 0.0, calibration: float = 0.0) -> None:
        self.loss_curve.append(float(loss))
        self.uncertainty_curve.append(float(uncertainty))
        self.calibration_curve.append(float(calibration))

    def latest(self) -> dict[str, float]:
        if not self.loss_curve:
            return {}
        return {
            "loss": self.loss_curve[-1],
            "uncertainty": self.uncertainty_curve[-1],
            "calibration": self.calibration_curve[-1],
        }


class UQHyperparameterOptimizer:
    def optimize(
        self,
        builder: Any,
        x: np.ndarray,
        y: np.ndarray,
        param_grid: dict[str, list[Any]],
        score_fn: Any,
    ) -> dict[str, Any]:
        keys = list(param_grid.keys())
        if not keys:
            model = builder()
            score = float(score_fn(model, x, y))
            return {"best_params": {}, "best_score": score}

        best_score = -float("inf")
        best_params: dict[str, Any] = {}

        def dfs(idx: int, current: dict[str, Any]) -> None:
            nonlocal best_score, best_params
            if idx >= len(keys):
                model = builder(**current)
                score = float(score_fn(model, x, y))
                if score > best_score:
                    best_score = score
                    best_params = dict(current)
                return
            key = keys[idx]
            for value in param_grid[key]:
                current[key] = value
                dfs(idx + 1, current)

        dfs(0, {})
        return {"best_params": best_params, "best_score": float(best_score)}


class UQModelSelector:
    def select(self, candidates: dict[str, dict[str, float]], key: str = "nll", lower_is_better: bool = True) -> tuple[str, dict[str, float]]:
        if not candidates:
            raise ValueError("候选模型为空")
        if lower_is_better:
            best_name = min(candidates.keys(), key=lambda k: candidates[k].get(key, float("inf")))
        else:
            best_name = max(candidates.keys(), key=lambda k: candidates[k].get(key, -float("inf")))
        return best_name, candidates[best_name]


class UQModelStore:
    def save(self, model: Any, path: str) -> str:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as fp:
            pickle.dump(model, fp)
        return str(output)

    def load(self, path: str) -> Any:
        with Path(path).open("rb") as fp:
            return pickle.load(fp)


class UQTrainingManager:
    def __init__(self) -> None:
        self.monitor = UQTrainingMonitor()
        self.optimizer = UQHyperparameterOptimizer()
        self.selector = UQModelSelector()
        self.store = UQModelStore()

    def build_model(self, config: UQTrainingConfig, in_dim: int) -> Any:
        if config.model_name == "bnn":
            prior = GaussianMixturePrior() if config.regularization > 0.08 else GaussianPrior(1.0)
            return BayesianNeuralRegressor(in_dim=in_dim, hidden_dim=config.hidden_dim, prior=prior)
        if config.model_name == "mc_dropout":
            return MCDropoutRegressor(
                MCDropoutConfig(
                    in_dim=in_dim,
                    hidden_dim=config.hidden_dim,
                    dropout_rate=min(0.5, 0.15 + config.regularization),
                    dropout_type="variational" if config.regularization > 0.08 else "standard",
                )
            )
        if config.model_name == "deep_ensemble":
            n_members = 5 if config.regularization < 0.1 else 7
            return DeepEnsembleRegressor(in_dim=in_dim, n_members=n_members)
        if config.model_name == "edl":
            return EDLClassifier(
                EDLConfig(
                    in_dim=in_dim,
                    num_classes=max(2, config.num_classes),
                    hidden_dim=config.hidden_dim,
                    evidence_activation="softplus",
                )
            )
        raise ValueError(f"不支持的模型: {config.model_name}")

    def _build_edl_labels(self, values: np.ndarray, num_classes: int) -> np.ndarray:
        y = np.asarray(values, dtype=float).reshape(-1)
        quantiles = np.percentile(y, np.linspace(0.0, 100.0, num_classes + 1))
        labels = np.zeros(len(y), dtype=int)
        for i in range(num_classes):
            left = quantiles[i]
            right = quantiles[i + 1]
            if i == num_classes - 1:
                mask = (y >= left) & (y <= right)
            else:
                mask = (y >= left) & (y < right)
            labels[mask] = i
        return labels

    def train(self, config: UQTrainingConfig, x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
        features = np.asarray(x, dtype=float)
        if features.ndim == 1:
            features = features.reshape(-1, 1)
        target = np.asarray(y, dtype=float).reshape(-1)
        if len(features) != len(target):
            raise ValueError("x 与 y 长度不一致")

        model = self.build_model(config, in_dim=features.shape[1])

        if config.model_name == "bnn":
            train_info = model.fit(
                features,
                target,
                epochs=config.max_epochs,
                lr=config.learning_rate,
                kl_anneal_epochs=max(20, config.max_epochs // 2),
            )
            pred = model.predict(features, num_samples=40)
            uncertainty = float(np.mean(pred["variance"]))
            calibration = float(np.mean(pred["epistemic"]))
            self.monitor.log(train_info["final_loss"], uncertainty=uncertainty, calibration=calibration)

        elif config.model_name == "mc_dropout":
            train_info = model.fit(
                features,
                target,
                epochs=config.max_epochs,
                lr=config.learning_rate,
                nll_weight=config.uncertainty_weight,
            )
            pred = model.predict(features, t=40)
            uncertainty = float(np.mean(pred["variance"]))
            calibration = float(np.mean(pred["epistemic"]))
            self.monitor.log(train_info["final_loss"], uncertainty=uncertainty, calibration=calibration)

        elif config.model_name == "deep_ensemble":
            train_info = model.fit(features, target, epochs=config.max_epochs)
            pred = model.predict(features, aggregation="mean")
            uncertainty = float(np.mean(pred["variance"]))
            diversity = model.model_diversity(features)["spread"]
            self.monitor.log(train_info["avg_val_nll"], uncertainty=uncertainty, calibration=diversity)

        else:
            labels = self._build_edl_labels(target, num_classes=max(2, config.num_classes))
            train_info = model.fit(
                features,
                labels,
                epochs=config.max_epochs,
                lr=config.learning_rate,
                evidence_weight=config.uncertainty_weight,
                kl_weight=config.regularization,
            )
            pred = model.predict(features)
            uncertainty = float(np.mean(pred["uncertainty"]["total"]))
            calibration = float(model.expected_calibration_error(pred["probabilities"], labels))
            self.monitor.log(train_info["final_loss"], uncertainty=uncertainty, calibration=calibration)

        return {
            "model": model,
            "training": train_info,
            "config": asdict(config),
            "monitor": self.monitor.latest(),
        }

    def tune(
        self,
        model_name: UQModelName,
        x: np.ndarray,
        y: np.ndarray,
        param_grid: dict[str, list[Any]],
    ) -> dict[str, Any]:
        features = np.asarray(x, dtype=float)
        if features.ndim == 1:
            features = features.reshape(-1, 1)
        target = np.asarray(y, dtype=float).reshape(-1)

        def builder(**kwargs: Any) -> Any:
            cfg = UQTrainingConfig(model_name=model_name, **kwargs)
            return self.build_model(cfg, in_dim=features.shape[1])

        def score_fn(model: Any, x_local: np.ndarray, y_local: np.ndarray) -> float:
            if model_name == "bnn":
                model.fit(x_local, y_local, epochs=80)
                pred = model.predict(x_local, num_samples=20)
                return -float(np.mean(pred["variance"]))
            if model_name == "mc_dropout":
                model.fit(x_local, y_local, epochs=80)
                pred = model.predict(x_local, t=20)
                return -float(np.mean(pred["variance"]))
            if model_name == "deep_ensemble":
                info = model.fit(x_local, y_local, epochs=80)
                return -float(info["avg_val_nll"])
            labels = self._build_edl_labels(y_local, num_classes=3)
            model.fit(x_local, labels, epochs=80)
            pred = model.predict(x_local)
            return -float(np.mean(pred["uncertainty"]["total"]))

        return self.optimizer.optimize(builder, features, target, param_grid, score_fn)
