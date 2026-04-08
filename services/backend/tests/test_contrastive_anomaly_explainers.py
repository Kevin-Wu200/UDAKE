"""Contrastive 异常解释适配器测试。"""

from __future__ import annotations

import numpy as np

from app.dl_services.contrastive_anomaly_explainer import ContrastiveLimeAdapter, ContrastiveShapAdapter
from deep_learning.models.anomaly_detection import ContrastiveAnomalyDetector


def _build_data() -> tuple[np.ndarray, np.ndarray]:
    coords = np.asarray(
        [
            [120.10, 30.20],
            [120.20, 30.25],
            [120.18, 30.30],
            [120.24, 30.28],
            [120.15, 30.35],
            [120.28, 30.22],
            [120.30, 30.26],
            [120.12, 30.18],
        ],
        dtype=float,
    )
    values = np.asarray([1.0, 1.1, 0.95, 1.3, 1.18, 2.2, 1.05, 0.98], dtype=float)
    return coords, values


def _build_trained_model() -> tuple[ContrastiveAnomalyDetector, np.ndarray, np.ndarray]:
    coords, values = _build_data()
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=12)
    return model, coords, values


def test_contrastive_lime_adapter_generates_explanations_and_cache() -> None:
    model, coords, values = _build_trained_model()
    adapter = ContrastiveLimeAdapter()
    first = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3)
    second = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3)

    assert first["summary"]["method"] == "lime"
    assert first["summary"]["explained_nodes"] == 3
    assert len(first["batch_explanations"]) == 3
    assert len(first["score_components"]["combined"]) == len(values)
    assert "encoder_components" in first
    assert "embedding_analysis" in first
    assert "anomaly_score_explanation" in first
    assert len(first["anomaly_score_explanation"]["decomposition"]) == len(values)
    assert len(first["anomaly_score_explanation"]["anomaly_reasons"]) == 3
    assert first["embedding_analysis"]["summary"]["embedding_count"] == len(values)
    assert "similarity" in first["embedding_analysis"]
    assert "distribution" in first["embedding_analysis"]
    assert "anomaly_patterns" in first["embedding_analysis"]
    assert len(first["embedding_analysis"]["visualization"]["points"]) == len(values)
    assert second["performance"]["cache_hit"] is True


def test_contrastive_shap_adapter_embedding_analysis() -> None:
    model, coords, values = _build_trained_model()
    adapter = ContrastiveShapAdapter()
    out = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3, nsamples=80)

    assert out["summary"]["method"] == "shap"
    assert "embedding_analysis" in out
    emb = out["embedding_analysis"]
    assert emb["summary"]["embedding_count"] == len(values)
    assert emb["summary"]["embedding_dim"] > 0
    assert emb["similarity"]["mean_cosine_similarity"] <= 1.0
    assert emb["distribution"]["embedding_dim"] > 0
    assert emb["anomaly_patterns"]["pattern_name"] in {"high_score_far_center_low_similarity", "none"}
    assert len(emb["visualization"]["points"]) == len(values)
