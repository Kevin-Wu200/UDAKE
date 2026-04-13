from __future__ import annotations

from deep_learning.fusion import (
    AdaptiveLearningMode,
    FusionConfig,
    FusionStrategy,
    ModelFusionEngine,
    ModelPrediction,
    WeightMethod,
)
from deep_learning.fusion.weighting import FusionWeightCalculator


def _models() -> list[ModelPrediction]:
    return [
        ModelPrediction(
            model_id="m1",
            predictions=[10.0, 10.8, 11.1, 11.3, 10.9, 11.0],
            variances=[0.09, 0.09, 0.08, 0.08, 0.10, 0.10],
        ),
        ModelPrediction(
            model_id="m2",
            predictions=[10.2, 10.6, 11.0, 11.4, 11.1, 11.2],
            variances=[0.06, 0.07, 0.07, 0.08, 0.08, 0.09],
        ),
        ModelPrediction(
            model_id="m3",
            predictions=[10.1, 10.7, 11.2, 11.2, 11.0, 11.1],
            variances=[0.07, 0.08, 0.09, 0.07, 0.09, 0.10],
        ),
    ]


def _truth() -> list[float]:
    return [10.1, 10.7, 11.1, 11.25, 11.0, 11.05]


def test_fusion_engine_result_cache_hit_stage1() -> None:
    engine = ModelFusionEngine(cache_size=16)
    cfg = FusionConfig(strategy=FusionStrategy.WEIGHTED_AVERAGE, weight_method=WeightMethod.ADAPTIVE)

    first = engine.fuse(models=_models(), config=cfg, true_values=_truth(), context={"difficulty": [1.0] * len(_truth())})
    second = engine.fuse(models=_models(), config=cfg, true_values=_truth(), context={"difficulty": [1.0] * len(_truth())})

    assert first.diagnostics["cache_hit"] is False
    assert second.diagnostics["cache_hit"] is True
    assert second.diagnostics["cache_metrics"]["hits"] >= 1
    assert second.diagnostics["cache_metrics"]["hit_rate"] > 0.0


def test_fusion_prediction_reuse_marks_stage1() -> None:
    engine = ModelFusionEngine()
    compared = engine.compare_strategies(
        models=_models(),
        true_values=_truth(),
        context={"difficulty": [1.0] * len(_truth())},
    )

    assert "weighted_average" in compared
    assert "dynamic" in compared
    for result in compared.values():
        reuse = result.diagnostics.get("prediction_reuse", {})
        assert reuse.get("matrix_reused") is True
        assert reuse.get("shape") == [3, 6]


def test_weight_calculator_cache_hit_stage1() -> None:
    engine = ModelFusionEngine(cache_size=4)
    cfg = FusionConfig(
        strategy=FusionStrategy.WEIGHTED_AVERAGE,
        weight_method=WeightMethod.ADAPTIVE,
        adaptive_mode=AdaptiveLearningMode.NEURAL,
    )
    first = engine.fuse(models=_models(), config=cfg, true_values=_truth(), context={"difficulty": [1.0] * len(_truth())})
    second = engine.fuse(models=_models(), config=cfg, true_values=_truth(), context={"difficulty": [0.8] * len(_truth())})

    assert first.diagnostics["cache_hit"] is False
    assert second.diagnostics["cache_hit"] is False
    assert first.diagnostics["weight_cache_hit"] is False
    assert second.diagnostics["weight_cache_hit"] is True
    assert second.diagnostics["weight_cache_metrics"]["hits"] >= 1


def test_weight_calculator_direct_cache_stage1() -> None:
    calculator = FusionWeightCalculator(cache_size=8)
    engine = ModelFusionEngine()
    metrics = engine.evaluator.evaluate_model_metrics(_models(), _truth())

    first = calculator.calculate(method=WeightMethod.ADAPTIVE, metrics=metrics)
    second = calculator.calculate(method=WeightMethod.ADAPTIVE, metrics=metrics)

    assert calculator.last_cache_hit is True
    assert first == second
    assert calculator.cache_metrics()["hits"] >= 1
