from __future__ import annotations

import numpy as np

from services.backend.app.dl_services.fusion_explainer import (
    FusionExplanationConfig,
    FusionLIMEAdapter,
    FusionSHAPAdapter,
)


def _models() -> list[dict]:
    return [
        {
            "model_id": "m1",
            "predictions": [10.0, 10.8, 11.1, 11.3, 10.9, 11.0],
            "variances": [0.09, 0.09, 0.08, 0.08, 0.10, 0.10],
        },
        {
            "model_id": "m2",
            "predictions": [10.2, 10.6, 11.0, 11.4, 11.1, 11.2],
            "variances": [0.06, 0.07, 0.07, 0.08, 0.08, 0.09],
        },
        {
            "model_id": "m3",
            "predictions": [10.1, 10.7, 11.2, 11.2, 11.0, 11.1],
            "variances": [0.07, 0.08, 0.09, 0.07, 0.09, 0.10],
        },
    ]


def _true_values() -> list[float]:
    return [10.1, 10.7, 11.1, 11.25, 11.0, 11.05]


def test_fusion_preprocess_predict_and_adapters_stage1() -> None:
    models = _models()
    truth = _true_values()

    lime_adapter = FusionLIMEAdapter(
        config=FusionExplanationConfig(lime_num_samples=100, max_explain_nodes=4, random_state=17)
    )
    pre = lime_adapter.preprocess_fusion_data(
        models=models,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=truth,
    )
    assert np.asarray(pre["matrix"], dtype=float).shape == (6, 3)
    assert len(pre["model_ids"]) == 3
    assert np.asarray(pre["fused_predictions"], dtype=float).shape == (6,)
    assert pre["preprocess"]["model_count"] == 3

    predict_fn = lime_adapter._predict_fusion_fn(pre)
    pred = np.asarray(predict_fn(np.asarray(pre["matrix"], dtype=float)), dtype=float).reshape(-1)
    assert pred.shape == (6,)

    lime = lime_adapter.explain(
        models=models,
        top_k=3,
        max_explain_nodes=4,
        num_samples=90,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=truth,
    )
    assert lime["summary"]["method"] == "lime"
    assert lime["summary"]["explained_nodes"] == 4
    assert len(lime["batch_explanations"]) == 4
    assert len(lime["global_feature_importance"]) == 3
    assert lime["preprocess"]["model_count"] == 3

    shap_adapter = FusionSHAPAdapter(
        config=FusionExplanationConfig(shap_nsamples=80, max_explain_nodes=4, random_state=19)
    )
    shap = shap_adapter.explain(
        models=models,
        top_k=3,
        max_explain_nodes=4,
        nsamples=70,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=truth,
    )
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 4
    assert shap["summary"]["nsamples"] == 70
    assert len(shap["batch_explanations"]) == 4
    assert len(shap["global_feature_importance"]) == 3
    assert "backend" in shap["explainer"]


def test_fusion_shap_adapter_cache_hit_stage1() -> None:
    models = _models()
    truth = _true_values()
    adapter = FusionSHAPAdapter(
        config=FusionExplanationConfig(shap_nsamples=70, max_explain_nodes=3, cache_size=4, random_state=23)
    )

    first = adapter.explain(
        models=models,
        top_k=3,
        max_explain_nodes=3,
        nsamples=60,
        strategy="weighted_average",
        weight_method="adaptive",
        true_values=truth,
    )
    second = adapter.explain(
        models=models,
        top_k=3,
        max_explain_nodes=3,
        nsamples=60,
        strategy="weighted_average",
        weight_method="adaptive",
        true_values=truth,
    )

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is True
    assert second["performance"]["result_cache_hit_rate"] > 0.3
