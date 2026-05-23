from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import GCAEAnomalyDetector
from services.backend.app.dl_services.gcae_anomaly_explainer import (
    GCAEExplanationConfig,
    GCAELimeAdapter,
    GCAEShapAdapter,
)


def _make_data(n: int = 84, seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.1) + np.cos(coords[:, 1] * 2.7) + rng.normal(0.0, 0.05, size=n)
    values[::13] += 0.9
    return coords, values


def test_gcae_lime_stage2_explanation_outputs() -> None:
    coords, values = _make_data()
    model = GCAEAnomalyDetector()
    model.fit(coords, values)

    adapter = GCAELimeAdapter(config=GCAEExplanationConfig(parallel_workers=2, lime_num_samples=180))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=6, num_samples=140)

    assert out["summary"]["method"] == "lime"
    assert "anomaly_score_explanation" in out
    assert "graph_structure_analysis" in out
    assert len(out["anomaly_score_explanation"]["decomposition"]) == len(values)
    assert len(out["anomaly_score_explanation"]["key_anomaly_nodes"]) >= 1
    assert "consistency_validation" in out["anomaly_score_explanation"]
    assert "structure_importance" in out["graph_structure_analysis"]
    assert "subgraph_features" in out["graph_structure_analysis"]
    assert out["performance"]["parallel_workers"] >= 1

    first = out["batch_explanations"][0]
    assert "decomposition" in first
    assert "reason" in first


def test_gcae_shap_stage2_explanation_outputs_and_cache() -> None:
    coords, values = _make_data(seed=17)
    model = GCAEAnomalyDetector()
    model.fit(coords, values)

    adapter = GCAEShapAdapter(config=GCAEExplanationConfig(parallel_workers=2, shap_nsamples=120, shap_feature_cap=6))
    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=5, nsamples=120)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=5, nsamples=120)

    assert out1["summary"]["method"] == "shap"
    assert out1["summary"]["nsamples"] <= 120
    assert "anomaly_score_explanation" in out1
    assert "graph_structure_analysis" in out1
    assert out2["performance"]["cache_hit"] is True
