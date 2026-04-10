"""异常检测示例公共工具。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import numpy as np

# 允许以 `python deep_learning/examples/*.py` 方式直接运行示例。
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from deep_learning.models.anomaly_detection import (
    ContrastiveAnomalyDetector,
    GANAnomalyDetector,
    GCAEAnomalyDetector,
    VAEAnomalyDetector,
)


@dataclass
class DemoDataset:
    coords: np.ndarray
    values: np.ndarray
    injected_indices: list[int]


def build_demo_dataset(
    n: int = 96,
    seed: int = 42,
    anomaly_ratio: float = 0.08,
) -> DemoDataset:
    """构建带可控异常点的空间数据集。"""
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    base = np.sin(coords[:, 0] * 4.8) + np.cos(coords[:, 1] * 3.2)
    noise = rng.normal(0.0, 0.05, size=n)
    values = base + noise

    inject_count = max(3, int(n * anomaly_ratio))
    injected = sorted(rng.choice(n, size=inject_count, replace=False).astype(int).tolist())
    for i, idx in enumerate(injected):
        sign = 1.0 if i % 2 == 0 else -1.0
        values[idx] += sign * (1.0 + 0.25 * rng.random())
    return DemoDataset(coords=coords, values=values, injected_indices=injected)


def summarize_prediction(prediction: dict[str, Any]) -> dict[str, Any]:
    anomaly_indices = [int(i) for i in prediction.get("anomaly_indices", [])]
    scores = np.asarray(prediction.get("anomaly_scores", prediction.get("scores", [])), dtype=float)
    top_score = float(scores.max()) if scores.size else 0.0
    return {
        "anomaly_count": int(prediction.get("anomaly_count", len(anomaly_indices))),
        "anomaly_indices": anomaly_indices[:10],
        "top_score": top_score,
    }


def create_model(model_name: str) -> Any:
    if model_name == "vae":
        return VAEAnomalyDetector()
    if model_name == "gcae":
        return GCAEAnomalyDetector()
    if model_name == "gan":
        return GANAnomalyDetector()
    if model_name == "contrastive":
        return ContrastiveAnomalyDetector()
    raise ValueError(f"unsupported model_name: {model_name}")


def train_model(model_name: str, model: Any, coords: np.ndarray, values: np.ndarray, epochs: int) -> dict[str, Any]:
    if model_name == "contrastive":
        return model.fit(coords, values, epochs=epochs)
    return model.fit(coords, values)


def quick_train_predict_workflow(
    model_name: str,
    dataset: DemoDataset,
    *,
    epochs: int = 12,
) -> dict[str, Any]:
    model = create_model(model_name)
    coords = dataset.coords
    values = dataset.values
    train_out = train_model(model_name, model, coords, values, epochs)
    predict_out = model.predict(
        coords=coords,
        values=values,
        threshold_method="percentile",
        percentile=92.0,
        k=2.2,
    )
    if hasattr(model, "predict_standard"):
        predict_standard_out = model.predict_standard(
            coords=coords,
            values=values,
            threshold_method="percentile",
            percentile=92.0,
            k=2.2,
        )
    else:
        predict_standard_out = {
            "anomaly_count": int(predict_out.get("anomaly_count", 0)),
            "anomaly_indices": list(predict_out.get("anomaly_indices", [])),
            "details": predict_out,
        }
    score_bundle = model.anomaly_scores(coords, values)

    extras: dict[str, Any] = {}
    if model_name == "vae":
        extras["latent_preview"] = model.latent_visualization(coords, values)[:5]
    elif model_name == "gcae":
        pre = model.preprocess_graph_data(coords, values, batch_size=24)
        extras["feature_names"] = pre["feature_names"][:6]
    elif model_name == "gan":
        pre = model.preprocess_gan_data(coords, values, batch_size=24, use_training_stats=True, noise_scale=0.02)
        extras["feature_names"] = pre["feature_names"][:6]
    elif model_name == "contrastive":
        pre = model.preprocess_contrastive_data(coords, values, batch_size=24, use_training_stats=True, augmentation=True)
        extras["feature_names"] = pre["feature_names"][:6]
        extras["online_update"] = model.online_update(coords[:24], values[:24])

    return {
        "model": model,
        "train": train_out,
        "predict": predict_out,
        "predict_standard": predict_standard_out,
        "score_bundle_keys": sorted(score_bundle.keys()),
        "extras": extras,
        "prediction_summary": summarize_prediction(predict_out),
    }
