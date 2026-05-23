"""高级用法示例：串联不确定性估计、融合推理与强化学习采样推荐。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deep_learning.fusion.service import FusionPlatformService
from deep_learning.models.sampling_rl import SamplingRLIntegrator
from deep_learning.models.uncertainty import (
    UncertaintyDatasetBuilder,
    UncertaintySystemIntegrator,
)


def _build_demo_series(seed: int = 2026, n_points: int = 180) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n_points, 2))
    values = np.sin(coords[:, 0] * 6.2) + np.cos(coords[:, 1] * 3.4) + rng.normal(0.0, 0.07, size=n_points)
    return coords, values


def _to_square_map(values: np.ndarray, fallback: float = 0.05) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    side = int(np.ceil(np.sqrt(max(1, arr.size))))
    out = np.full((side * side,), float(fallback), dtype=float)
    out[: arr.size] = arr
    return out.reshape(side, side)


def _json_float(v: Any) -> float:
    if isinstance(v, (np.floating, np.integer)):
        return float(v)
    return float(v)


def main() -> None:
    coords, values = _build_demo_series()
    dataset = UncertaintyDatasetBuilder(seed=2026).create_uncertainty_dataset(coords, values)

    sample_coords = dataset.coords[:130]
    sample_values = dataset.values[:130]
    query_coords = dataset.coords[130:]
    query_true = dataset.values[130:]

    # 1) 不确定性估计：先拿到预测均值与方差，为后续融合和采样提供输入。
    uq = UncertaintySystemIntegrator()
    uq_result = uq.predict(sample_coords, sample_values, query_coords, method="deep_ensemble")
    mean = np.asarray(uq_result.mean, dtype=float).reshape(-1)
    variance = np.clip(np.asarray(uq_result.variance, dtype=float).reshape(-1), 1e-6, None)

    rng = np.random.default_rng(2048)
    residual_scale = np.sqrt(variance)
    model_a = mean + 0.05 + rng.normal(0.0, residual_scale * 0.35)
    model_b = mean - 0.03 + rng.normal(0.0, residual_scale * 0.30)
    model_c = mean + rng.normal(0.0, residual_scale * 0.45)

    models = [
        {
            "model_id": "uq_base_a",
            "model_name": "deep_ensemble_a",
            "predictions": [float(v) for v in model_a.tolist()],
            "variances": [float(v) for v in (variance * 0.90 + 0.005).tolist()],
            "metadata": {"source": "advanced_demo"},
        },
        {
            "model_id": "uq_base_b",
            "model_name": "deep_ensemble_b",
            "predictions": [float(v) for v in model_b.tolist()],
            "variances": [float(v) for v in (variance * 1.05 + 0.004).tolist()],
            "metadata": {"source": "advanced_demo"},
        },
        {
            "model_id": "uq_base_c",
            "model_name": "deep_ensemble_c",
            "predictions": [float(v) for v in model_c.tolist()],
            "variances": [float(v) for v in (variance * 1.15 + 0.006).tolist()],
            "metadata": {"source": "advanced_demo"},
        },
    ]
    context = {
        "confidence_boost": [float(1.0 / (1.0 + v)) for v in variance.tolist()],
        "uncertainty_signal": [float(v) for v in variance.tolist()],
    }

    # 2) 融合服务：基于不确定性感知上下文训练融合配置并执行推理。
    with TemporaryDirectory(prefix="advanced_fusion_") as tmp_dir:
        fusion_service = FusionPlatformService(repository_dir=tmp_dir)
        profile_id = "advanced_usage_profile"
        train_out = fusion_service.train_fusion_profile(
            profile_id=profile_id,
            models=models,
            true_values=[float(v) for v in query_true.tolist()],
            strategy="dynamic",
            weight_method="adaptive",
            adaptive_mode="neural",
            context=context,
        )
        inference_out = fusion_service.inference(
            models=models,
            profile_id=profile_id,
            true_values=[float(v) for v in query_true.tolist()],
            context=context,
        )

    # 3) 强化学习采样：把不确定性分布转为二维网格，输出下一轮采样点建议。
    rl_integrator = SamplingRLIntegrator(model_name="ppo", seed=99)
    uncertainty_map = np.clip(_to_square_map(variance, fallback=0.05), 0.01, 1.0)
    rec_out = rl_integrator.recommend(uncertainty_map=uncertainty_map, n_recommendations=6, realtime=True)

    summary = {
        "advanced_usage_demo": {
            "uq": {
                "query_count": int(mean.size),
                "variance_mean": _json_float(np.mean(variance)),
                "variance_p90": _json_float(np.quantile(variance, 0.9)),
            },
            "fusion": {
                "profile_id": profile_id,
                "strategy": str(inference_out["selected_strategy"]),
                "rmse": _json_float(inference_out["result"]["metrics"]["rmse"]),
                "trained_weights": {k: _json_float(v) for k, v in dict(train_out["profile"]["weights"]).items()},
            },
            "sampling": {
                "map_shape": list(uncertainty_map.shape),
                "recommendations": rec_out["recommendations"][:3],
            },
        }
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
