from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import EDLClassifier, EDLConfig
from services.backend.app.dl_services.edl_explainer import (
    EDLExplanationConfig,
    EDLLIMEAdapter,
    EDLSHAPAdapter,
)


def _make_features(n: int = 56, seed: int = 23) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.2) + np.cos(coords[:, 1] * 3.7) + rng.normal(0.0, 0.05, size=n)
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def _make_labels(values: np.ndarray, classes: int = 3) -> np.ndarray:
    bins = np.percentile(values, np.linspace(0.0, 100.0, classes + 1))
    y = np.zeros(len(values), dtype=int)
    for i in range(classes):
        left, right = bins[i], bins[i + 1]
        if i == classes - 1:
            mask = (values >= left) & (values <= right)
        else:
            mask = (values >= left) & (values < right)
        y[mask] = i
    return y


def test_edl_preprocess_predict_and_adapters_stage1() -> None:
    x = _make_features(n=48)
    y = _make_labels(x[:, 2], classes=3)

    model = EDLClassifier(EDLConfig(in_dim=3, num_classes=3, hidden_dim=18, evidence_activation="softplus", seed=31))
    train = model.fit(x, y, epochs=90, lr=7e-3)
    assert train["epochs"] == 90

    pre = model.preprocess_edl_data(x, use_training_stats=False)
    assert np.asarray(pre["processed_features"], dtype=float).shape == (48, 3)
    assert len(pre["feature_names"]) == 3
    assert pre["validation"]["is_valid"] is True

    pred = model.predict_edl(x, confidence=0.9, use_training_stats=True)
    assert np.asarray(pred["probabilities"], dtype=float).shape == (48, 3)
    assert np.asarray(pred["prediction"], dtype=int).shape == (48,)
    assert np.asarray(pred["uncertainty"]["total"], dtype=float).shape == (48,)
    assert "preprocess" in pred
    assert pred["preprocess"]["validation"]["is_valid"] is True

    lime_adapter = EDLLIMEAdapter(config=EDLExplanationConfig(lime_num_samples=90, max_explain_nodes=4))
    lime = lime_adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=4, num_samples=80)
    assert lime["summary"]["method"] == "lime"
    assert lime["summary"]["explained_nodes"] == 4
    assert len(lime["batch_explanations"]) == 4
    assert len(lime["global_feature_importance"]) == 3
    assert "scaler" in lime["preprocess"]

    shap_adapter = EDLSHAPAdapter(config=EDLExplanationConfig(shap_nsamples=80, max_explain_nodes=4))
    shap = shap_adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=4, nsamples=70)
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 4
    assert shap["summary"]["nsamples"] == 70
    assert len(shap["batch_explanations"]) == 4
    assert len(shap["global_feature_importance"]) == 3
    assert "backend" in shap["explainer"]


def test_edl_shap_adapter_cache_hit_stage1() -> None:
    x = _make_features(n=40, seed=47)
    y = _make_labels(x[:, 2], classes=3)

    model = EDLClassifier(EDLConfig(in_dim=3, num_classes=3, hidden_dim=16, evidence_activation="relu", seed=53))
    model.fit(x, y, epochs=80, lr=7e-3)

    adapter = EDLSHAPAdapter(config=EDLExplanationConfig(shap_nsamples=60, max_explain_nodes=3, cache_size=4))
    first = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=3, nsamples=55)
    second = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=3, nsamples=55)

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is True
    assert second["performance"]["result_cache_hit_rate"] > 0.3
