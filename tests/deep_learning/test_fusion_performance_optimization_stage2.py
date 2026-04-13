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


def test_fusion_lime_batch_explain_and_batch_cache_stage2() -> None:
    adapter = FusionLIMEAdapter(
        config=FusionExplanationConfig(lime_num_samples=100, max_explain_nodes=4, cache_size=10, random_state=211)
    )

    models_batch = [_models(), _models(), _models()]
    true_values_batch = [_true_values(), _true_values(), _true_values()]
    context_batch = [{"difficulty": [1.0] * len(_true_values())} for _ in models_batch]

    out1 = adapter.explain_batch(
        models_batch=models_batch,
        top_k=4,
        max_explain_nodes=4,
        num_samples=88,
        strategy="dynamic",
        weight_method="adaptive",
        true_values_batch=true_values_batch,
        context_batch=context_batch,
    )
    out2 = adapter.explain_batch(
        models_batch=models_batch,
        top_k=4,
        max_explain_nodes=4,
        num_samples=88,
        strategy="dynamic",
        weight_method="adaptive",
        true_values_batch=true_values_batch,
        context_batch=context_batch,
    )

    assert out1["summary"]["method"] == "lime"
    assert out1["summary"]["batch_size"] == 3
    assert out1["summary"]["cache_hit_count"] >= 2
    assert out2["performance"]["batch_cache_hit"] is True
    assert out2["performance"]["batch_result_cache_hits"] >= 1


def test_fusion_memory_optimization_metrics_stage2() -> None:
    adapter = FusionLIMEAdapter(
        config=FusionExplanationConfig(lime_num_samples=96, max_explain_nodes=5, max_background_size=12, random_state=223)
    )
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

    perf = out["performance"]
    assert perf["context_memory_bytes"] > 0
    assert perf["estimated_raw_context_memory_bytes"] >= perf["context_memory_bytes"]
    assert 0.0 <= perf["context_memory_saved_ratio"] <= 1.0
    assert out["explainer"]["context_cache_hit"] is False


def test_fusion_shap_batch_result_cache_metrics_stage2() -> None:
    adapter = FusionSHAPAdapter(
        config=FusionExplanationConfig(shap_nsamples=92, max_explain_nodes=4, cache_size=10, random_state=227)
    )
    models_batch = [_models(), _models()]

    out1 = adapter.explain_batch(
        models_batch=models_batch,
        top_k=4,
        max_explain_nodes=4,
        nsamples=72,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )
    out2 = adapter.explain_batch(
        models_batch=models_batch,
        top_k=4,
        max_explain_nodes=4,
        nsamples=72,
        strategy="dynamic",
        weight_method="adaptive",
        true_values=_true_values(),
        context={"difficulty": [1.0] * len(_true_values())},
    )

    assert out1["summary"]["method"] == "shap"
    assert out1["summary"]["batch_size"] == 2
    assert out1["summary"]["cache_hit_count"] >= 1
    assert out2["performance"]["batch_cache_hit"] is True
    assert out2["performance"]["batch_result_cache_hit_rate"] > 0.0
