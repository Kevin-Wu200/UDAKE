"""融合模型解释适配器使用示例。"""

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
from services.backend.app.dl_services.fusion_explainer import (
    FusionExplanationConfig,
    FusionLIMEAdapter,
    FusionSHAPAdapter,
)


def _build_demo_payload(seed: int = 2026, n_steps: int = 24) -> tuple[list[dict[str, Any]], list[float], dict[str, list[float]]]:
    rng = np.random.default_rng(seed)
    axis = np.linspace(0.0, 4.0 * np.pi, n_steps)
    truth = 1.5 + 0.7 * np.sin(axis) + 0.18 * np.cos(axis * 0.55)

    models: list[dict[str, Any]] = []
    templates = [
        ("kriging_base", "kriging", 0.10, 0.020, -0.020),
        ("st_transformer", "st_transformer", 0.07, 0.018, 0.012),
        ("gnn_residual", "gnn_residual", 0.12, 0.028, 0.018),
    ]
    for idx, (model_id, model_name, noise_scale, var_base, bias) in enumerate(templates):
        pred = truth + bias + rng.normal(0.0, noise_scale, size=n_steps)
        variance = np.clip(
            var_base + 0.008 * np.abs(np.sin(axis + idx * 0.3)) + rng.normal(0.0, 0.0025, size=n_steps),
            0.002,
            0.2,
        )
        models.append(
            {
                "model_id": model_id,
                "model_name": model_name,
                "predictions": [float(v) for v in pred.tolist()],
                "variances": [float(v) for v in variance.tolist()],
                "metadata": {"source": "demo", "version": "v1"},
            }
        )

    context = {
        "confidence_boost": [float(0.5 + 0.5 * np.sin(i / max(1, n_steps - 1) * np.pi)) for i in range(n_steps)],
        "weather_impact": [float(0.2 + 0.1 * np.cos(i / max(1, n_steps - 1) * 2.0 * np.pi)) for i in range(n_steps)],
    }
    return models, [float(v) for v in truth.tolist()], context


def _summary_row(result: dict[str, Any]) -> dict[str, Any]:
    top_feature = result["summary"]["top_features"][0] if result["summary"]["top_features"] else {}
    return {
        "explained_nodes": int(result["summary"]["explained_nodes"]),
        "top_feature": str(top_feature.get("feature_name", "")),
        "importance": float(top_feature.get("importance", 0.0)),
        "latency_ms": float(result["performance"]["latency_ms"]),
        "backend": str(result["explainer"].get("backend", "surrogate_linear")),
        "cache_hit": bool(result["performance"]["cache_hit"]),
    }


def _as_text(value: Any) -> str:
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    return str(value)


def main() -> None:
    models, true_values, context = _build_demo_payload()

    with TemporaryDirectory(prefix="fusion_demo_") as tmp_dir:
        service = FusionPlatformService(repository_dir=tmp_dir)
        profile_id = "fusion_demo_profile"

        train_result = service.train_fusion_profile(
            profile_id=profile_id,
            models=models,
            true_values=true_values,
            strategy="dynamic",
            weight_method="adaptive",
            adaptive_mode="neural",
            context=context,
        )
        predict_result = service.inference(models=models, profile_id=profile_id, true_values=true_values, context=context)
        recommend_result = service.recommend_strategy(models=models, true_values=true_values, context=context, objective="balanced")

        config = FusionExplanationConfig(lime_num_samples=120, shap_nsamples=80, max_explain_nodes=6, random_state=42)
        lime_adapter = FusionLIMEAdapter(config)
        shap_adapter = FusionSHAPAdapter(config)
        lime_out = lime_adapter.explain(
            models=models,
            top_k=4,
            max_explain_nodes=6,
            num_samples=120,
            profile_id=profile_id,
            true_values=true_values,
            context=context,
        )
        shap_out = shap_adapter.explain(
            models=models,
            top_k=4,
            max_explain_nodes=6,
            nsamples=80,
            profile_id=profile_id,
            true_values=true_values,
            context=context,
        )

    payload = {
        "fusion_adapter_usage_example": {
            "profile_id": profile_id,
            "trained_strategy": _as_text(train_result["profile"]["strategy"]),
            "trained_weight_method": _as_text(train_result["profile"]["weight_method"]),
            "trained_weights": dict(train_result["profile"]["weights"]),
            "inference_strategy": str(predict_result["selected_strategy"]),
            "inference_rmse": float(predict_result["result"]["metrics"]["rmse"]),
            "recommended_strategy": str(recommend_result["recommended_strategy"]),
            "lime": _summary_row(lime_out),
            "shap": _summary_row(shap_out),
            "monitor": service.monitor_status(),
        }
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
