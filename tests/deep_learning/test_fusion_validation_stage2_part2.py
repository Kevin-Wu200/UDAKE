from __future__ import annotations

import math

import pytest

from deep_learning.fusion.service import FusionPlatformService
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


def test_stage2_part2_validate_submodel_contribution_analysis() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=120, max_explain_nodes=6, random_state=131))
    out = adapter.explain(
        models=_models(),
        top_k=4,
        max_explain_nodes=6,
        num_samples=96,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )

    ranking = out["submodel_contribution_ranking"]
    rows = ranking["ranking"]
    assert ranking["summary"]["model_count"] == 4
    assert ranking["summary"]["top_contributor"] == rows[0]["model_id"]
    assert len(rows) == 4
    assert all(0.0 <= row["contribution_score"] <= 1.0 for row in rows)
    assert rows[0]["contribution_score"] >= rows[-1]["contribution_score"]

    selection = out["submodel_selection_recommendation"]
    assert selection["summary"]["recommended_count"] >= 1
    assert all(item["reason"] for item in selection["recommended_models"])


def test_stage2_part2_validate_fusion_strategy_explanation() -> None:
    adapter = FusionSHAPAdapter(config=FusionExplanationConfig(shap_nsamples=84, max_explain_nodes=5, random_state=137))
    out = adapter.explain(
        models=_models(),
        top_k=4,
        max_explain_nodes=5,
        nsamples=70,
        strategy="bagging",
        weight_method="adaptive",
        true_values=_true_values(),
    )

    strategy = out["strategy_selection_explanation"]
    summary = strategy["summary"]
    assert summary["requested_strategy"] == "bagging"
    assert summary["effective_strategy"] == "simple_average"
    assert summary["selected_strategy"] != ""
    assert "bagging_alias_simple_average" in summary["reason_tags"]

    active = strategy["active_strategy_explanation"]
    assert active["strategy"] == "bagging"
    explanations = strategy["strategy_explanations"]
    assert {"weighted_average", "dynamic", "stacking", "bagging"} <= set(explanations.keys())


def test_stage2_part2_performance_benchmark_with_cache_hit() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=105, max_explain_nodes=5, cache_size=8, random_state=139))
    params = {
        "models": _models(),
        "top_k": 4,
        "max_explain_nodes": 5,
        "num_samples": 90,
        "strategy": "dynamic",
        "weight_method": "adaptive",
        "true_values": _true_values(),
        "context": {"difficulty": [1.0] * len(_true_values())},
    }

    first = adapter.explain(**params)
    second = adapter.explain(**params)

    perf_first = first["performance"]
    perf_second = second["performance"]

    assert perf_first["cache_hit"] is False
    assert perf_second["cache_hit"] is True
    assert perf_second["result_cache_hits"] >= 1
    assert perf_second["latency_ms"] >= 0.0
    assert perf_second["meets_latency_target"] is True


def test_stage2_part2_boundary_conditions_for_fusion_adapter() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=90, max_explain_nodes=5, random_state=149))

    with pytest.raises(ValueError, match="models cannot be empty"):
        adapter.preprocess_fusion_data(models=[])

    mismatched_models = [
        {"model_id": "m1", "predictions": [1.0, 2.0]},
        {"model_id": "m2", "predictions": [1.0]},
    ]
    with pytest.raises(ValueError, match="same length"):
        adapter.preprocess_fusion_data(models=mismatched_models)

    with pytest.raises(ValueError, match="true_values length mismatch"):
        adapter.preprocess_fusion_data(models=[{"model_id": "m1", "predictions": [1.0, 2.0]}], true_values=[1.0])

    out = adapter.explain(
        models=_models(),
        top_k=99,
        max_explain_nodes=99,
        num_samples=70,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
    )
    assert out["summary"]["explained_nodes"] == len(_true_values())
    assert len(out["summary"]["top_features"]) == len(_models())


def test_stage2_part2_fusion_effect_comparison() -> None:
    service = FusionPlatformService(repository_dir="/tmp/fusion_validation_stage2_part2_repo")
    comparison = service.evaluate_strategy_effectiveness(
        models=_models(),
        strategy="dynamic",
        baseline_strategy="weighted_average",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )

    assert comparison["target_strategy"] == "dynamic"
    assert comparison["baseline_strategy"] == "weighted_average"

    effectiveness = comparison["effectiveness"]
    assert effectiveness["has_ground_truth"] is True
    assert effectiveness["level"] in {"excellent", "good", "fair", "weak"}

    delta = effectiveness["improvement_vs_baseline"]
    assert "rmse_improvement_pct" in delta
    assert "r2_gain" in delta
    assert "mae_improvement_pct" in delta

    assert math.isfinite(float(effectiveness["score"]))
    assert math.isfinite(float(delta["rmse_improvement_pct"]))
