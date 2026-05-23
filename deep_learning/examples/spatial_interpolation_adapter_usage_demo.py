"""空间插值模型解释适配器使用示例。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deep_learning.models.spatial_interpolation import (
    AttentionKrigingModel,
    GNNKrigingModel,
    ResidualKrigingModel,
)
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset
from services.backend.app.dl_services.attention_kriging_explainer import (
    AttentionKrigingExplanationConfig,
    AttentionKrigingLIMEAdapter,
    AttentionKrigingSHAPAdapter,
)
from services.backend.app.dl_services.gnn_kriging_explainer import (
    GNNKrigingExplanationConfig,
    GNNKrigingLIMEAdapter,
    GNNKrigingSHAPAdapter,
)
from services.backend.app.dl_services.residual_kriging_explainer import (
    ResidualKrigingExplanationConfig,
    ResidualKrigingLIMEAdapter,
    ResidualKrigingSHAPAdapter,
)


def _make_data(seed: int = 2026, n_points: int = 64) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    payload = SyntheticSpatialDataset(seed=seed).generate(n_points=n_points, noise_std=0.03)
    coords = np.asarray(payload["coords"], dtype=float)
    values = np.asarray(payload["values"], dtype=float)
    query_coords = coords[:20]
    return coords, values, query_coords


def _extract_summary(name: str, lime_out: dict[str, Any], shap_out: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": name,
        "query_count": int(len(lime_out["score_components"]["prediction"])),
        "lime": {
            "explained_nodes": int(lime_out["summary"]["explained_nodes"]),
            "top_feature": (
                lime_out["summary"]["top_features"][0]["feature_name"] if lime_out["summary"]["top_features"] else None
            ),
            "duration_ms": float(lime_out["performance"]["duration_ms"]),
            "cache_hit": bool(lime_out["performance"]["cache_hit"]),
        },
        "shap": {
            "explained_nodes": int(shap_out["summary"]["explained_nodes"]),
            "top_feature": (
                shap_out["summary"]["top_features"][0]["feature_name"] if shap_out["summary"]["top_features"] else None
            ),
            "backend": str(shap_out["performance"].get("backend", "surrogate_linear")),
            "duration_ms": float(shap_out["performance"]["duration_ms"]),
            "cache_hit": bool(shap_out["performance"]["cache_hit"]),
        },
    }


def main() -> None:
    sample_coords, sample_values, query_coords = _make_data()
    outputs: list[dict[str, Any]] = []

    gnn_model = GNNKrigingModel(hidden_dim=12)
    gnn_lime = GNNKrigingLIMEAdapter(
        config=GNNKrigingExplanationConfig(lime_num_samples=120, shap_nsamples=90, max_explain_nodes=4)
    )
    gnn_shap = GNNKrigingSHAPAdapter(
        config=GNNKrigingExplanationConfig(lime_num_samples=120, shap_nsamples=90, max_explain_nodes=4)
    )
    gnn_lime_out = gnn_lime.explain(
        model=gnn_model,
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords,
        top_k=4,
        num_samples=100,
    )
    gnn_shap_out = gnn_shap.explain(
        model=gnn_model,
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords,
        top_k=4,
        nsamples=80,
    )
    outputs.append(_extract_summary("GNN-Kriging", gnn_lime_out, gnn_shap_out))

    attention_model = AttentionKrigingModel(dim=24)
    attention_lime = AttentionKrigingLIMEAdapter(
        config=AttentionKrigingExplanationConfig(lime_num_samples=120, shap_nsamples=90, max_explain_nodes=4)
    )
    attention_shap = AttentionKrigingSHAPAdapter(
        config=AttentionKrigingExplanationConfig(lime_num_samples=120, shap_nsamples=90, max_explain_nodes=4)
    )
    attention_lime_out = attention_lime.explain(
        model=attention_model,
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords,
        top_k=4,
        num_samples=100,
    )
    attention_shap_out = attention_shap.explain(
        model=attention_model,
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords,
        top_k=4,
        nsamples=80,
    )
    outputs.append(_extract_summary("Attention-Kriging", attention_lime_out, attention_shap_out))

    residual_model = ResidualKrigingModel(architecture="hybrid")
    residual_lime = ResidualKrigingLIMEAdapter(
        config=ResidualKrigingExplanationConfig(lime_num_samples=120, shap_nsamples=90, max_explain_nodes=4)
    )
    residual_shap = ResidualKrigingSHAPAdapter(
        config=ResidualKrigingExplanationConfig(lime_num_samples=120, shap_nsamples=90, max_explain_nodes=4)
    )
    residual_lime_out = residual_lime.explain(
        model=residual_model,
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords,
        top_k=4,
        num_samples=100,
    )
    residual_shap_out = residual_shap.explain(
        model=residual_model,
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords,
        top_k=4,
        nsamples=80,
    )
    outputs.append(_extract_summary("Residual-Kriging", residual_lime_out, residual_shap_out))

    print(json.dumps({"adapter_usage_examples": outputs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
