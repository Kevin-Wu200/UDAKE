from __future__ import annotations

from deep_learning.fusion import AdaptiveFusionSystem, FusionConfig, FusionStrategy, ModelPrediction, WeightMethod


def _fault_models() -> list[ModelPrediction]:
    return [
        ModelPrediction(
            model_id="stable_a",
            predictions=[10.0, 10.2, 10.1, 10.3, 10.2, 10.1],
            variances=[0.08, 0.08, 0.08, 0.09, 0.08, 0.08],
        ),
        ModelPrediction(
            model_id="stable_b",
            predictions=[9.9, 10.1, 10.2, 10.2, 10.3, 10.2],
            variances=[0.07, 0.07, 0.07, 0.08, 0.08, 0.07],
        ),
        ModelPrediction(
            model_id="faulty",
            predictions=[10.0, 10.0, 10.0, 40.0, 10.0, 10.0],
            variances=[2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        ),
    ]


def test_fusion_stage5_fault_detection_and_adaptive_strategy() -> None:
    adaptive = AdaptiveFusionSystem()
    y = [10.0, 10.1, 10.1, 10.25, 10.2, 10.15]
    payload = adaptive.online_fuse(models=_fault_models(), true_values=y)

    assert payload["selected_strategy"] in {"median", "dynamic"}
    assert payload["model_health"]["faulty"]["status"] == "fault"
    assert payload["online_weights"]["faulty"] < payload["online_weights"]["stable_a"]
    assert payload["online_weights"]["faulty"] < payload["online_weights"]["stable_b"]
    assert len(payload["fault_events"]) >= 1


def test_fusion_stage5_realtime_weight_adjustment() -> None:
    adaptive = AdaptiveFusionSystem(ema_alpha=0.5)
    models = [
        ModelPrediction(model_id="m1", predictions=[1.0, 1.1, 0.9, 1.0]),
        ModelPrediction(model_id="m2", predictions=[2.0, 1.9, 2.1, 2.0]),
    ]
    cfg = FusionConfig(strategy=FusionStrategy.WEIGHTED_AVERAGE, weight_method=WeightMethod.EQUAL)

    out1 = adaptive.online_fuse(models=models, base_config=cfg, true_values=[1.0, 1.0, 1.1, 0.9])
    out2 = adaptive.online_fuse(models=models, base_config=cfg, true_values=[2.0, 2.1, 1.9, 2.0])

    assert out1["online_weights"]["m1"] > out1["online_weights"]["m2"]
    assert out2["online_weights"]["m2"] > out1["online_weights"]["m2"]
    assert abs(sum(out2["realtime_adjustment"]["performance_weights"].values()) - 1.0) < 1e-6


def test_fusion_stage5_monitor_contains_fault_summary() -> None:
    adaptive = AdaptiveFusionSystem()
    _ = adaptive.online_fuse(
        models=_fault_models(),
        true_values=[10.0, 10.1, 10.2, 10.2, 10.1, 10.0],
    )
    status = adaptive.monitor()
    assert "fault_summary" in status
    assert status["fault_summary"]["recent_faults"] >= 1
    assert "faulty" in status["fault_summary"]["unhealthy_models"]
