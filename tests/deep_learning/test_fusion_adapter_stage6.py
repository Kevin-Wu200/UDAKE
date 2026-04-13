from __future__ import annotations

from services.backend.app.dl_services.fusion_explainer import (
    FusionExplanationConfig,
    FusionLIMEAdapter,
    FusionSHAPAdapter,
)


def _models_with_faulty() -> list[dict]:
    return [
        {
            "model_id": "stable_a",
            "predictions": [10.0, 10.2, 10.1, 10.3, 10.2, 10.1, 10.15, 10.18],
            "variances": [0.08, 0.08, 0.08, 0.09, 0.08, 0.08, 0.08, 0.08],
        },
        {
            "model_id": "stable_b",
            "predictions": [9.95, 10.15, 10.25, 10.24, 10.31, 10.22, 10.26, 10.2],
            "variances": [0.07, 0.07, 0.07, 0.08, 0.08, 0.07, 0.07, 0.07],
        },
        {
            "model_id": "faulty",
            "predictions": [10.0, 10.1, 10.2, 40.0, 10.1, 10.2, 33.0, 10.1],
            "variances": [2.0, 2.1, 2.0, 2.3, 2.0, 2.1, 2.4, 2.0],
        },
        {
            "model_id": "candidate_plus",
            "predictions": [10.02, 10.18, 10.16, 10.25, 10.24, 10.19, 10.21, 10.2],
            "variances": [0.05, 0.05, 0.05, 0.06, 0.06, 0.05, 0.05, 0.05],
        },
    ]


def _models_stabilized() -> list[dict]:
    rows = _models_with_faulty()
    rows[2]["predictions"] = [10.1, 10.1, 10.2, 10.2, 10.15, 10.12, 10.18, 10.2]
    rows[2]["variances"] = [0.12, 0.11, 0.12, 0.12, 0.11, 0.11, 0.12, 0.11]
    return rows


def _true_values() -> list[float]:
    return [10.0, 10.15, 10.2, 10.25, 10.22, 10.18, 10.2, 10.19]


def _assert_stage6_payload(payload: dict) -> None:
    assert "model_auto_replacement" in payload
    assert "fusion_history_record" in payload
    assert "fusion_effect_prediction" in payload

    sub = payload["submodel_analysis"]
    assert "model_auto_replacement" in sub
    assert "fusion_history_record" in sub
    assert "fusion_effect_prediction" in sub

    replacement = payload["model_auto_replacement"]
    assert "summary" in replacement
    assert "actions" in replacement
    assert replacement["summary"]["candidate_count"] >= 0
    for row in replacement["actions"]:
        assert "target_model_id" in row
        assert "candidate_model_id" in row
        assert row["recommended_action"] in {"replace_now", "shadow_deploy", "observe_only"}

    history = payload["fusion_history_record"]
    assert history["summary"]["history_count"] >= 1
    assert "recent_records" in history
    assert len(history["recent_records"]) >= 1

    effect = payload["fusion_effect_prediction"]
    assert "summary" in effect
    assert "drivers" in effect
    assert effect["summary"]["level"] in {"high", "medium", "neutral", "negative"}
    assert 0.0 <= effect["summary"]["confidence"] <= 1.0


def test_fusion_lime_stage6_model_management_history_and_effect_prediction() -> None:
    adapter = FusionLIMEAdapter(
        config=FusionExplanationConfig(
            lime_num_samples=110,
            max_explain_nodes=5,
            random_state=81,
            management_history_limit=32,
        )
    )
    out1 = adapter.explain(
        models=_models_with_faulty(),
        top_k=4,
        max_explain_nodes=5,
        num_samples=90,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    _assert_stage6_payload(out1)

    out2 = adapter.explain(
        models=_models_stabilized(),
        top_k=4,
        max_explain_nodes=5,
        num_samples=90,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [0.9] * len(_true_values())},
    )
    _assert_stage6_payload(out2)
    assert out2["fusion_history_record"]["summary"]["history_count"] >= 2


def test_fusion_shap_stage6_model_management_history_and_effect_prediction() -> None:
    adapter = FusionSHAPAdapter(
        config=FusionExplanationConfig(
            shap_nsamples=88,
            max_explain_nodes=5,
            random_state=83,
            management_history_limit=32,
        )
    )
    out = adapter.explain(
        models=_models_with_faulty(),
        top_k=4,
        max_explain_nodes=5,
        nsamples=72,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    _assert_stage6_payload(out)
