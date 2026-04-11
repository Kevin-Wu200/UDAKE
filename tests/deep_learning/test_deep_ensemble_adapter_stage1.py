from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import DeepEnsembleRegressor
from services.backend.app.dl_services.deep_ensemble_explainer import (
    DeepEnsembleExplanationConfig,
    DeepEnsembleLIMEAdapter,
    DeepEnsembleSHAPAdapter,
)


def _make_features(n: int = 48, seed: int = 23) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.2) + np.cos(coords[:, 1] * 3.7) + rng.normal(0.0, 0.05, size=n)
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def test_deep_ensemble_preprocess_predict_and_adapters_stage1() -> None:
    x = _make_features(n=44)
    y = np.asarray(x[:, 2], dtype=float) + 0.15 * np.asarray(x[:, 0], dtype=float)

    model = DeepEnsembleRegressor(in_dim=3, n_members=4, seed=31)
    train = model.fit(x, y, epochs=80)
    assert train["n_members"] == 4

    pre = model.preprocess_deep_ensemble_data(x, use_training_stats=False)
    assert np.asarray(pre["processed_features"], dtype=float).shape == (44, 3)
    assert len(pre["feature_names"]) == 3
    assert pre["validation"]["is_valid"] is True

    pred = model.predict_deep_ensemble(x, aggregation="mean", confidence=0.9, use_training_stats=True)
    assert np.asarray(pred["mean"], dtype=float).shape == (44,)
    assert np.asarray(pred["variance"], dtype=float).shape == (44,)
    assert pred["aggregation"] == "mean"
    assert pred["member_count"] == 4
    assert "preprocess" in pred
    assert pred["preprocess"]["validation"]["is_valid"] is True

    lime_adapter = DeepEnsembleLIMEAdapter(
        config=DeepEnsembleExplanationConfig(lime_num_samples=90, max_explain_nodes=4)
    )
    lime = lime_adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=4, num_samples=80)
    assert lime["summary"]["method"] == "lime"
    assert lime["summary"]["explained_nodes"] == 4
    assert len(lime["batch_explanations"]) == 4
    assert len(lime["global_feature_importance"]) == 3
    assert "scaler" in lime["preprocess"]
    assert lime["ensemble"]["member_count"] == 4

    shap_adapter = DeepEnsembleSHAPAdapter(
        config=DeepEnsembleExplanationConfig(shap_nsamples=80, max_explain_nodes=4)
    )
    shap = shap_adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=4, nsamples=70)
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 4
    assert shap["summary"]["nsamples"] == 70
    assert len(shap["batch_explanations"]) == 4
    assert len(shap["global_feature_importance"]) == 3
    assert "backend" in shap["explainer"]


def test_deep_ensemble_shap_adapter_cache_hit_stage1() -> None:
    x = _make_features(n=36, seed=47)
    y = np.asarray(x[:, 2], dtype=float) - 0.2 * np.asarray(x[:, 1], dtype=float)
    model = DeepEnsembleRegressor(in_dim=3, n_members=4, seed=53)
    model.fit(x, y, epochs=70)

    adapter = DeepEnsembleSHAPAdapter(
        config=DeepEnsembleExplanationConfig(shap_nsamples=60, max_explain_nodes=3, cache_size=4)
    )
    first = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=3, nsamples=55)
    second = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=3, nsamples=55)

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is True
    assert second["performance"]["result_cache_hit_rate"] > 0.3
