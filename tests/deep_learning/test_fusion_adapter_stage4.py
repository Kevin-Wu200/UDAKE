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


def _assert_stage4_payload(payload: dict) -> None:
    assert "submodel_contribution_ranking" in payload
    assert "submodel_selection_recommendation" in payload
    assert "submodel_alternative_solutions" in payload

    submodel_analysis = payload["submodel_analysis"]
    assert "submodel_contribution_ranking" in submodel_analysis
    assert "submodel_selection_recommendation" in submodel_analysis
    assert "submodel_alternative_solutions" in submodel_analysis

    contribution = payload["submodel_contribution_ranking"]
    assert contribution["summary"]["model_count"] == 4
    assert contribution["summary"]["top_contributor"] != ""
    assert len(contribution["ranking"]) == 4
    assert all(0.0 <= row["contribution_score"] <= 1.0 for row in contribution["ranking"])

    selection = payload["submodel_selection_recommendation"]
    assert selection["summary"]["model_count"] == 4
    assert selection["summary"]["recommended_count"] >= 1
    assert len(selection["recommended_models"]) >= 1
    assert all("reason" in row for row in selection["recommended_models"])

    alternatives = payload["submodel_alternative_solutions"]
    assert "replacement_plans" in alternatives
    assert "global_alternative_pool" in alternatives
    assert len(alternatives["global_alternative_pool"]) >= 1


def test_fusion_lime_stage4_submodel_recommendation() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=120, max_explain_nodes=5, random_state=71))
    out = adapter.explain(
        models=_models(),
        top_k=4,
        max_explain_nodes=5,
        num_samples=95,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    assert out["summary"]["method"] == "lime"
    _assert_stage4_payload(out)


def test_fusion_shap_stage4_submodel_recommendation() -> None:
    adapter = FusionSHAPAdapter(config=FusionExplanationConfig(shap_nsamples=90, max_explain_nodes=5, random_state=73))
    out = adapter.explain(
        models=_models(),
        top_k=4,
        max_explain_nodes=5,
        nsamples=76,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    assert out["summary"]["method"] == "shap"
    _assert_stage4_payload(out)
