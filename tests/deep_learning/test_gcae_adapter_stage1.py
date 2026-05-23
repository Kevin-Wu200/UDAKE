from __future__ import annotations

import numpy as np
import pytest

from deep_learning.models.anomaly_detection import GCAEAnomalyDetector
from services.backend.app.dl_services.gcae_anomaly_explainer import (
    GCAELimeAdapter,
    GCAEShapAdapter,
)
from services.backend.app.dl_services.service import DeepLearningService


def _make_data(n: int = 72, seed: int = 29) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.5) + np.cos(coords[:, 1] * 3.2) + rng.normal(0.0, 0.06, size=n)
    values[::11] += 0.8
    return coords, values


def test_gcae_preprocess_and_standard_predict() -> None:
    coords, values = _make_data()
    model = GCAEAnomalyDetector()

    with pytest.raises(ValueError):
        model.predict_standard(coords, values)

    model.fit(coords, values)
    pre = model.preprocess_graph_data(coords, values, batch_size=16)
    assert pre["validation"]["is_valid"] is True
    assert len(pre["feature_names"]) == 11
    assert np.asarray(pre["processed_features"], dtype=float).shape == (len(values), 11)
    assert len(pre["batch_slices"]) >= 2

    pred = model.predict_standard(coords, values, threshold_method="percentile", percentile=92.0)
    assert len(pred["scores"]) == len(values)
    assert len(pred["labels"]) == len(values)
    assert pred["anomaly_count"] == len(pred["anomaly_indices"])


def test_gcae_lime_and_shap_adapters() -> None:
    coords, values = _make_data()
    model = GCAEAnomalyDetector()
    model.fit(coords, values)

    lime_adapter = GCAELimeAdapter()
    lime = lime_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=120)
    assert lime["summary"]["method"] == "lime"
    assert lime["summary"]["explained_nodes"] == 5
    assert len(lime["global_feature_importance"]) >= 1
    assert "batch_slices" in lime["preprocess"]

    shap_adapter = GCAEShapAdapter()
    shap = shap_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=80)
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 5
    assert len(shap["global_feature_importance"]) >= 1
    assert "adjacency_shape" in shap["preprocess"]


def test_service_supports_gcae_explain() -> None:
    coords, values = _make_data(n=60, seed=31)
    service = DeepLearningService()

    out = service.explain_anomaly(
        model_name="gcae",
        coords=coords.tolist(),
        values=values.tolist(),
        method="hybrid",
        top_k=4,
        max_explain_nodes=4,
        include_prediction=True,
        num_samples=120,
        nsamples=80,
    )
    assert out["model_name"] == "gcae"
    assert out["summary"]["method"] == "hybrid"
    assert "lime" in out
    assert "shap" in out
    assert "prediction" in out
