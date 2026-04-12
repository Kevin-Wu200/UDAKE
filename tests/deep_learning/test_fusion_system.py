from __future__ import annotations

from pathlib import Path

from deep_learning.fusion import (
    AdaptiveFusionSystem,
    AdaptiveLearningMode,
    FusionConfig,
    FusionFeatureAnalyzer,
    FusionModelManager,
    FusionPlatformService,
    FusionStrategy,
    ModelFusionEngine,
    ModelPrediction,
    WeightMethod,
)


def _sample_models() -> list[ModelPrediction]:
    return [
        ModelPrediction(
            model_id="m1",
            predictions=[10.0, 10.8, 11.1, 11.3, 10.9, 11.0],
            variances=[0.09, 0.09, 0.08, 0.08, 0.1, 0.1],
        ),
        ModelPrediction(
            model_id="m2",
            predictions=[10.2, 10.6, 11.0, 11.4, 11.1, 11.2],
            variances=[0.06, 0.07, 0.07, 0.08, 0.08, 0.09],
        ),
        ModelPrediction(
            model_id="m3",
            predictions=[10.1, 10.7, 11.2, 11.2, 11.0, 11.1],
            variances=[0.07, 0.08, 0.09, 0.07, 0.09, 0.1],
        ),
    ]


def _sample_true() -> list[float]:
    return [10.1, 10.7, 11.1, 11.25, 11.0, 11.05]


def test_fusion_engine_all_strategies() -> None:
    engine = ModelFusionEngine()
    models = _sample_models()
    y = _sample_true()

    for strategy in FusionStrategy:
        cfg = FusionConfig(
            strategy=strategy,
            weight_method=WeightMethod.ADAPTIVE,
            adaptive_mode=AdaptiveLearningMode.ATTENTION,
            n_folds=3,
            enable_uncertainty=True,
        )
        result = engine.fuse(models=models, config=cfg, true_values=y, context={"difficulty": [1.0] * len(y)})
        assert len(result.fused_predictions) == len(y)
        assert len(result.weights) == len(models)
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6
        assert "rmse" in result.metrics


def test_fusion_weight_methods() -> None:
    engine = ModelFusionEngine()
    models = _sample_models()
    y = _sample_true()

    for method in WeightMethod:
        cfg = FusionConfig(
            strategy=FusionStrategy.WEIGHTED_AVERAGE,
            weight_method=method,
            adaptive_mode=AdaptiveLearningMode.NEURAL,
            n_folds=4,
        )
        result = engine.fuse(models=models, config=cfg, true_values=y)
        assert len(result.weights) == len(models)
        assert abs(sum(result.weights.values()) - 1.0) < 1e-6


def test_adaptive_fusion_online_update() -> None:
    adaptive = AdaptiveFusionSystem()
    models = _sample_models()
    y = _sample_true()

    out1 = adaptive.online_fuse(models=models, true_values=y)
    out2 = adaptive.online_fuse(models=models, true_values=y, context={"difficulty": [0.8] * len(y)})

    assert "result" in out1
    assert "online_weights" in out2
    assert len(out2["online_weights"]) == len(models)


def test_model_manager_workflow(tmp_path: Path) -> None:
    manager = FusionModelManager(root_dir=str(tmp_path / "fusion_repo"))
    manager.register_builder("demo_builder", lambda gain=1.0: {"gain": gain})

    model = manager.create_model("demo_builder", gain=2.0)
    reg = manager.store_model(
        model_id="fusion_meta",
        model_obj=model,
        model_type="meta",
        metrics={"rmse": 0.1},
        config={"strategy": "weighted_average"},
    )

    assert reg.version == "v1"
    lazy_obj = manager.load_model("fusion_meta")
    assert lazy_obj["path"].endswith("model.pkl")

    real_obj = manager.load_model("fusion_meta", lazy=False)
    assert real_obj["gain"] == 2.0

    validation = manager.validate_model("fusion_meta")
    assert validation["ok"] is True
    assert "md5" in validation["integrity"]

    export_path = manager.export_model("fusion_meta", export_format="onnx")
    assert Path(export_path).exists()

    reg_b = manager.store_model(
        model_id="fusion_meta_b",
        model_obj={"gain": 3.0},
        model_type="meta",
        metrics={"rmse": 0.2},
    )
    deployment = manager.deploy_ab_test(("fusion_meta", None), ("fusion_meta_b", reg_b.version), traffic_split=0.7)
    assert deployment["model_a"]["ratio"] == 0.7


def test_fusion_platform_service_end_to_end(tmp_path: Path) -> None:
    service = FusionPlatformService(repository_dir=str(tmp_path / "repo"))
    models = [
        {
            "model_id": m.model_id,
            "predictions": m.predictions,
            "variances": m.variances,
        }
        for m in _sample_models()
    ]
    y = _sample_true()

    train = service.train_fusion_profile(
        profile_id="default",
        models=models,
        true_values=y,
        strategy="dynamic",
        weight_method="adaptive",
        adaptive_mode="neural",
    )
    assert train["profile"]["profile_id"] == "default"

    infer = service.inference(models=models, profile_id="default", true_values=y)
    assert "result" in infer
    assert len(infer["result"]["fused_predictions"]) == len(y)

    cmp_result = service.compare_strategies(models=models, true_values=y)
    assert "weighted_average" in cmp_result
    assert "dynamic" in cmp_result

    opt = service.optimize_weights(models=models, true_values=y, strategy="weighted_average")
    assert opt["best_method"] is not None

    hybrid = service.hybrid_fusion(
        kriging_prediction=[1.0, 2.0, 3.0],
        deep_prediction=[1.2, 1.9, 3.1],
        mode="residual",
    )
    assert len(hybrid["prediction"]) == 3

    multimodal = service.multimodal_fusion(
        modalities=[[1.0, 2.0], [1.2, 2.3], [0.9, 2.1]],
        strategy="hybrid",
    )
    assert len(multimodal["fused"]) == 2

    access = service.check_access(token="internal-token", client_id="ut")
    assert access["ok"] is True

    status = service.monitor_status()
    assert status["requests"]["total"] >= 1


def test_fusion_platform_strategy_analysis_recommend_and_effectiveness(tmp_path: Path) -> None:
    service = FusionPlatformService(repository_dir=str(tmp_path / "repo"))
    models = [
        {
            "model_id": m.model_id,
            "predictions": m.predictions,
            "variances": m.variances,
        }
        for m in _sample_models()
    ]
    y = _sample_true()

    analysis = service.strategy_analysis(models=models, true_values=y, context={"difficulty": [1.0] * len(y)})
    assert "strategies" in analysis
    assert "analysis" in analysis
    assert analysis["analysis"]["best_strategy"] in analysis["strategies"]
    assert len(analysis["analysis"]["ranking"]) >= 1

    recommendation = service.recommend_strategy(
        models=models,
        true_values=y,
        context={"difficulty": [1.0] * len(y)},
        objective="rmse",
    )
    assert recommendation["objective"] == "rmse"
    assert recommendation["recommended_strategy"] in analysis["strategies"]
    assert len(recommendation["candidates"]) >= 1

    effectiveness = service.evaluate_strategy_effectiveness(
        models=models,
        strategy="dynamic",
        true_values=y,
        context={"difficulty": [1.0] * len(y)},
        baseline_strategy="weighted_average",
    )
    assert effectiveness["target_strategy"] == "dynamic"
    assert effectiveness["baseline_strategy"] == "weighted_average"
    assert "effectiveness" in effectiveness
    assert "improvement_vs_baseline" in effectiveness["effectiveness"]
    assert effectiveness["effectiveness"]["level"] in {"excellent", "good", "fair", "weak"}


def test_fusion_feature_analysis_design() -> None:
    engine = ModelFusionEngine()
    analyzer = FusionFeatureAnalyzer()
    models = _sample_models()
    y = _sample_true()
    result = engine.fuse(
        models=models,
        config=FusionConfig(strategy=FusionStrategy.DYNAMIC, weight_method=WeightMethod.ADAPTIVE),
        true_values=y,
        context={"difficulty": [1.0] * len(y)},
    )
    payload = analyzer.analyze(
        models=models,
        weights=result.weights,
        strategy=result.strategy,
        weight_method=result.weight_method,
        fused_predictions=result.fused_predictions,
        true_values=y,
        diagnostics=result.diagnostics,
    )
    assert payload["basic_features"]["model_count"] == len(models)
    assert payload["basic_features"]["prediction_horizon"] == len(y)
    assert payload["weight_features"]["weight_method"] == result.weight_method
    assert abs(sum(payload["weight_features"]["weights"].values()) - 1.0) < 1e-6
    assert len(payload["model_contributions"]) == len(models)
    assert "weight_scheme" in payload
    assert "contribution_scheme" in payload
    assert "strategy_features" in payload
