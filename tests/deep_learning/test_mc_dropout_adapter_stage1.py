from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import MCDropoutConfig, MCDropoutRegressor
from services.backend.app.dl_services.mc_dropout_explainer import (
    MCDropoutExplanationConfig,
    MCDropoutLIMEAdapter,
    MCDropoutSHAPAdapter,
)


def _make_features(n: int = 48, seed: int = 23) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.2) + np.cos(coords[:, 1] * 3.7) + rng.normal(0.0, 0.05, size=n)
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def test_mc_dropout_preprocess_predict_and_adapters_stage1() -> None:
    x = _make_features(n=44)
    y = np.asarray(x[:, 2], dtype=float) + 0.15 * np.asarray(x[:, 0], dtype=float)

    model = MCDropoutRegressor(
        MCDropoutConfig(in_dim=3, hidden_dim=16, dropout_rate=0.2, dropout_type="variational", seed=31)
    )
    train = model.fit(x, y, epochs=70, lr=7e-3)
    assert train["epochs"] == 70

    pre = model.preprocess_mc_dropout_data(x, use_training_stats=False)
    assert np.asarray(pre["processed_features"], dtype=float).shape == (44, 3)
    assert len(pre["feature_names"]) == 3
    assert pre["validation"]["is_valid"] is True

    pred = model.predict_mc_dropout(x, t=26, confidence=0.9, use_training_stats=True)
    assert np.asarray(pred["mean"], dtype=float).shape == (44,)
    assert np.asarray(pred["variance"], dtype=float).shape == (44,)
    assert pred["t"] == 26
    assert "preprocess" in pred
    assert pred["preprocess"]["validation"]["is_valid"] is True

    lime_adapter = MCDropoutLIMEAdapter(config=MCDropoutExplanationConfig(lime_num_samples=90, max_explain_nodes=4))
    lime = lime_adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=4, num_samples=80)
    assert lime["summary"]["method"] == "lime"
    assert lime["summary"]["explained_nodes"] == 4
    assert len(lime["batch_explanations"]) == 4
    assert len(lime["global_feature_importance"]) == 3
    assert "scaler" in lime["preprocess"]

    shap_adapter = MCDropoutSHAPAdapter(config=MCDropoutExplanationConfig(shap_nsamples=80, max_explain_nodes=4))
    shap = shap_adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=4, nsamples=70)
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 4
    assert shap["summary"]["nsamples"] == 70
    assert len(shap["batch_explanations"]) == 4
    assert len(shap["global_feature_importance"]) == 3
    assert "backend" in shap["explainer"]


def test_mc_dropout_shap_adapter_cache_hit_stage1() -> None:
    x = _make_features(n=36, seed=47)
    y = np.asarray(x[:, 2], dtype=float) - 0.2 * np.asarray(x[:, 1], dtype=float)
    model = MCDropoutRegressor(
        MCDropoutConfig(in_dim=3, hidden_dim=14, dropout_rate=0.22, dropout_type="standard", seed=53)
    )
    model.fit(x, y, epochs=60, lr=7e-3)

    adapter = MCDropoutSHAPAdapter(
        config=MCDropoutExplanationConfig(shap_nsamples=60, max_explain_nodes=3, cache_size=4)
    )
    first = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=3, nsamples=55)
    second = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=3, nsamples=55)

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is True
    assert second["performance"]["result_cache_hit_rate"] > 0.3
