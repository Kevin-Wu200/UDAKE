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


def _assert_stage3_payload(payload: dict) -> None:
    assert "submodel_analysis" in payload
    assert "submodel_performance_comparison" in payload
    assert "submodel_stability_analysis" in payload
    assert "submodel_complementarity_analysis" in payload
    assert "submodel_weight_visualization" in payload

    submodel_analysis = payload["submodel_analysis"]
    assert "submodel_performance_comparison" in submodel_analysis
    assert "submodel_stability_analysis" in submodel_analysis
    assert "submodel_complementarity_analysis" in submodel_analysis
    assert "submodel_weight_visualization" in submodel_analysis

    performance = payload["submodel_performance_comparison"]
    assert performance["summary"]["model_count"] == 4
    assert performance["summary"]["has_ground_truth"] is True
    assert len(performance["ranking"]) == 4
    assert all("score" in row for row in performance["ranking"])

    stability = payload["submodel_stability_analysis"]
    assert stability["summary"]["model_count"] == 4
    assert stability["summary"]["window_size"] >= 2
    assert len(stability["ranking"]) == 4
    assert all(0.0 <= row["overall_stability"] <= 1.0 for row in stability["ranking"])

    complementarity = payload["submodel_complementarity_analysis"]
    assert complementarity["summary"]["model_count"] == 4
    assert complementarity["summary"]["pair_count"] == 6
    assert len(complementarity["pair_scores"]) == 6
    heatmap = complementarity["complementarity_heatmap"]
    assert len(heatmap["model_ids"]) == 4
    assert len(heatmap["matrix"]) == 4
    assert all(len(row) == 4 for row in heatmap["matrix"])

    weights = payload["submodel_weight_visualization"]
    assert weights["summary"]["model_count"] == 4
    assert 0.0 <= weights["summary"]["weight_entropy"]
    assert len(weights["weight_distribution"]) == 4
    viz = weights["visualization_payload"]
    assert len(viz["bar_chart"]) == 4
    assert len(viz["pie_chart"]) == 4
    assert "timeline_chart" in viz


def test_fusion_lime_stage3_submodel_analysis() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=120, max_explain_nodes=5, random_state=61))
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
    _assert_stage3_payload(out)


def test_fusion_shap_stage3_submodel_analysis() -> None:
    adapter = FusionSHAPAdapter(config=FusionExplanationConfig(shap_nsamples=88, max_explain_nodes=5, random_state=67))
    out = adapter.explain(
        models=_models(),
        top_k=4,
        max_explain_nodes=5,
        nsamples=72,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    assert out["summary"]["method"] == "shap"
    _assert_stage3_payload(out)
