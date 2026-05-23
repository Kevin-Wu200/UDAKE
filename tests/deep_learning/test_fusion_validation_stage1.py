from __future__ import annotations

import numpy as np

from deep_learning.fusion.common import ModelMetric, WeightMethod
from deep_learning.fusion.service import FusionPlatformService
from deep_learning.fusion.weighting import FusionWeightCalculator
from services.backend.app.dl_services.fusion_explainer import (
    FusionExplanationConfig,
    FusionLIMEAdapter,
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
    ]


def _true_values() -> list[float]:
    return [10.1, 10.7, 11.1, 11.25, 11.0, 11.05, 11.2, 11.1]


def test_fusion_adapter_unit_stage1() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=100, max_explain_nodes=4, random_state=101))
    payload = adapter.preprocess_fusion_data(
        models=_models(),
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    assert np.asarray(payload["matrix"], dtype=float).shape == (8, 3)
    assert np.asarray(payload["fused_predictions"], dtype=float).shape == (8,)
    assert len(payload["model_ids"]) == 3
    assert abs(sum(payload["weights"].values()) - 1.0) < 1e-6
    assert payload["preprocess"]["model_count"] == 3


def test_fusion_strategy_analysis_stage1() -> None:
    service = FusionPlatformService(repository_dir="/tmp/fusion_validation_repo_strategy")
    analysis = service.strategy_analysis(
        models=_models(),
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    ranking = analysis["analysis"]["ranking"]
    assert len(ranking) >= 2
    assert analysis["analysis"]["best_strategy"] == ranking[0]["strategy"]
    assert ranking[0]["score"] >= ranking[-1]["score"]

    rec = service.recommend_strategy(
        models=_models(),
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
        objective="rmse",
    )
    assert rec["objective"] == "rmse"
    candidates = rec["candidates"]
    assert len(candidates) >= 1
    assert rec["recommended_strategy"] == candidates[0]["strategy"]
    assert candidates[0]["rmse"] <= max(row["rmse"] for row in candidates)


def test_submodel_analysis_stage1() -> None:
    adapter = FusionLIMEAdapter(config=FusionExplanationConfig(lime_num_samples=100, max_explain_nodes=5, random_state=103))
    out = adapter.explain(
        models=_models(),
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
        top_k=3,
        max_explain_nodes=5,
        num_samples=90,
    )
    assert "submodel_analysis" in out
    assert "submodel_performance_comparison" in out
    assert "submodel_stability_analysis" in out
    assert "submodel_complementarity_analysis" in out
    assert "submodel_weight_visualization" in out
    assert out["submodel_performance_comparison"]["summary"]["model_count"] == 3
    assert len(out["submodel_contribution_ranking"]["ranking"]) == 3


def test_fusion_integration_stage1(tmp_path) -> None:
    service = FusionPlatformService(repository_dir=str(tmp_path / "fusion_repo"))
    models = _models()
    y = _true_values()

    train = service.train_fusion_profile(
        profile_id="validation_stage1",
        models=models,
        true_values=y,
        strategy="dynamic",
        weight_method="adaptive",
        context={"difficulty": [1.0] * len(y)},
    )
    assert train["profile"]["profile_id"] == "validation_stage1"
    assert abs(sum(train["profile"]["weights"].values()) - 1.0) < 1e-6

    infer = service.inference(models=models, profile_id="validation_stage1", true_values=y)
    assert len(infer["result"]["fused_predictions"]) == len(y)
    assert len(infer["result"]["weights"]) == len(models)
    assert infer["selected_strategy"] != ""

    feature = service.feature_analysis(models=models, profile_id="validation_stage1", true_values=y)
    assert "analysis" in feature
    assert feature["analysis"]["basic_features"]["model_count"] == len(models)


def test_fusion_weight_calculation_accuracy_stage1() -> None:
    calculator = FusionWeightCalculator()
    metrics = [
        ModelMetric(model_id="m1", rmse=1.0, mae=0.8, r2=0.7, mape=6.0, stability=0.9, uncertainty=0.2),
        ModelMetric(model_id="m2", rmse=2.0, mae=1.6, r2=0.5, mape=9.0, stability=0.7, uncertainty=0.4),
        ModelMetric(model_id="m3", rmse=4.0, mae=3.2, r2=0.2, mape=15.0, stability=0.5, uncertainty=0.8),
    ]

    weights = calculator.calculate(method=WeightMethod.RMSE_BASED, metrics=metrics)
    expected_raw = np.asarray([1.0, 1.0 / 4.0, 1.0 / 16.0], dtype=float)
    expected = expected_raw / np.sum(expected_raw)
    got = np.asarray([weights["m1"], weights["m2"], weights["m3"]], dtype=float)

    assert np.allclose(got, expected, atol=1e-12)
    assert abs(sum(weights.values()) - 1.0) < 1e-12
    assert weights["m1"] > weights["m2"] > weights["m3"]
