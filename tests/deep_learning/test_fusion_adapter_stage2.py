from __future__ import annotations

from services.backend.app.dl_services.fusion_explainer import (
    FusionExplanationConfig,
    FusionLIMEAdapter,
    FusionSHAPAdapter,
)


def _models() -> list[dict]:
    return [
        {
            "model_id": "m1",
            "predictions": [10.0, 10.8, 11.1, 11.3, 10.9, 11.0, 11.2, 11.1],
            "variances": [0.09, 0.09, 0.08, 0.08, 0.10, 0.10, 0.09, 0.09],
        },
        {
            "model_id": "m2",
            "predictions": [10.2, 10.6, 11.0, 11.4, 11.1, 11.2, 11.0, 11.2],
            "variances": [0.06, 0.07, 0.07, 0.08, 0.08, 0.09, 0.08, 0.07],
        },
        {
            "model_id": "m3",
            "predictions": [10.1, 10.7, 11.2, 11.2, 11.0, 11.1, 11.3, 11.0],
            "variances": [0.07, 0.08, 0.09, 0.07, 0.09, 0.10, 0.08, 0.09],
        },
        {
            "model_id": "m4",
            "predictions": [10.05, 10.75, 11.15, 11.28, 11.02, 11.04, 11.18, 11.06],
            "variances": [0.05, 0.06, 0.06, 0.06, 0.07, 0.07, 0.06, 0.06],
        },
    ]


def _true_values() -> list[float]:
    return [10.1, 10.7, 11.1, 11.25, 11.0, 11.05, 11.2, 11.1]


def _assert_stage2_payload(payload: dict) -> None:
    assert "fusion_weight_analysis" in payload
    assert "submodel_contribution_analysis" in payload
    assert "strategy_selection_explanation" in payload

    weight = payload["fusion_weight_analysis"]
    assert weight["summary"]["model_count"] >= 3
    assert weight["summary"]["effective_model_count"] >= 1.0
    assert len(weight["weight_distribution"]) >= 3
    assert len(weight["top_weight_shift_models"]) >= 1

    contribution = payload["submodel_contribution_analysis"]
    assert contribution["summary"]["model_count"] >= 3
    assert contribution["summary"]["sample_count"] >= 1
    assert contribution["summary"]["explained_nodes"] >= 1
    assert len(contribution["global_contribution_ranking"]) >= 3
    assert len(contribution["per_node"]) >= 1

    strategy = payload["strategy_selection_explanation"]
    assert strategy["summary"]["selected_strategy"] != ""
    assert strategy["summary"]["weight_method"] != ""
    assert len(strategy["summary"]["reason_tags"]) >= 1
    assert "rmse" in strategy["evidence"]

    perf = payload["performance"]
    assert perf["sample_count"] >= 1
    assert perf["feature_dim"] >= 3
    assert perf["context_build_ms"] >= 0.0
    assert perf["context_memory_bytes"] > 0
    assert perf["result_memory_bytes"] >= 0


def test_fusion_lime_stage2_weight_contribution_strategy_and_performance() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=110, max_explain_nodes=5, random_state=31))
    out = adapter.explain(
        models=_models(),
        top_k=4,
        max_explain_nodes=5,
        num_samples=90,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 5
    _assert_stage2_payload(out)


def test_fusion_shap_stage2_weight_contribution_strategy_and_performance() -> None:
    adapter = FusionSHAPAdapter(config=FusionExplanationConfig(shap_nsamples=86, max_explain_nodes=5, random_state=37))
    out = adapter.explain(
        models=_models(),
        top_k=4,
        max_explain_nodes=5,
        nsamples=70,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    assert out["summary"]["method"] == "shap"
    assert out["summary"]["explained_nodes"] == 5
    assert out["summary"]["nsamples"] == 70
    _assert_stage2_payload(out)


def test_fusion_lime_stage2_context_cache_hit_when_result_cache_miss() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=100, max_explain_nodes=4, cache_size=6, random_state=43))
    first = adapter.explain(
        models=_models(),
        top_k=3,
        max_explain_nodes=4,
        num_samples=80,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    second = adapter.explain(
        models=_models(),
        top_k=5,
        max_explain_nodes=4,
        num_samples=80,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is False
    assert second["performance"]["context_cache_hit"] is True
    assert second["performance"]["context_cache_hits"] >= 1
