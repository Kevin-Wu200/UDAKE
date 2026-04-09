from __future__ import annotations

import asyncio

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from deep_learning.models.anomaly_detection import GANAnomalyDetector
from services.backend.app.dl_services.api import router
from services.backend.app.dl_services.gan_anomaly_explainer import GANAnomalyLimeAdapter, GANAnomalySHAPAdapter, GANExplanationConfig
from services.backend.app.dl_services.service import DeepLearningService


def _make_data(n: int = 128, seed: int = 47) -> tuple[np.ndarray, np.ndarray, set[int]]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.2) + np.cos(coords[:, 1] * 4.6) + rng.normal(0.0, 0.05, size=n)
    injected = {6, 29, 61, 95}
    for idx in injected:
        values[idx] += 1.25
    values[5::23] -= 0.75
    return coords, values, injected


def test_gan_end_to_end_detection_explain_generator_discriminator_and_accuracy() -> None:
    coords, values, injected = _make_data()
    service = DeepLearningService()

    train_out = service.train_anomaly_model("gan", coords.tolist(), values.tolist(), epochs=18)
    predict_out = service.predict_anomaly(
        "gan",
        coords.tolist(),
        values.tolist(),
        threshold_method="percentile",
        percentile=90.0,
        k=2.3,
    )
    explain_out = service.explain_anomaly(
        model_name="gan",
        coords=coords.tolist(),
        values=values.tolist(),
        method="hybrid",
        top_k=5,
        max_explain_nodes=7,
        include_prediction=True,
        num_samples=180,
        nsamples=120,
    )

    assert train_out["model_name"] == "gan"
    assert train_out["training"]["epochs"] >= 1
    assert predict_out["model_name"] == "gan"
    assert "prediction" in predict_out
    assert "score_preview" in predict_out

    prediction = predict_out["prediction"]
    assert "score_components" in prediction
    assert "training_diagnostics" in prediction
    components = prediction["score_components"]
    diagnostics = prediction["training_diagnostics"]
    assert "discriminator" in components
    assert "reconstruction" in components
    assert "gradient" in components
    assert len(components["discriminator"]) == len(values)
    assert len(components["reconstruction"]) == len(values)
    assert len(components["gradient"]) == len(values)
    assert len(diagnostics["generator_loss"]) >= 1
    assert len(diagnostics["discriminator_loss"]) >= 1

    assert explain_out["summary"]["method"] == "hybrid"
    assert "lime" in explain_out
    assert "shap" in explain_out
    assert "prediction" in explain_out
    assert "generator_analysis" in explain_out["lime"]
    assert "discriminator_analysis" in explain_out["lime"]
    assert "generator_analysis" in explain_out["shap"]
    assert "discriminator_analysis" in explain_out["shap"]

    model = service.anomaly_models["gan"]
    assert isinstance(model, GANAnomalyDetector)
    prep = model.preprocess_gan_data(coords, values, batch_size=24)
    assert prep["validation"]["is_valid"] is True
    assert len(prep["feature_names"]) == 9
    assert np.asarray(prep["processed_features"], dtype=float).shape == (len(values), 9)
    assert len(prep["batch_slices"]) >= 2

    scores = np.asarray(prediction["anomaly_scores"], dtype=float)
    injected_scores = np.asarray([scores[idx] for idx in sorted(injected)], dtype=float)
    normal_indices = [idx for idx in range(len(scores)) if idx not in injected]
    normal_scores = np.asarray([scores[idx] for idx in normal_indices], dtype=float)
    assert injected_scores.mean() > normal_scores.mean()


def test_gan_api_frontend_contract_and_async_integration() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    coords, values, _ = _make_data(seed=59)
    coords_list = coords.tolist()
    values_list = values.tolist()

    train_resp = client.post(
        "/api/dl/anomaly/train",
        json={"model_name": "gan", "coords": coords_list, "values": values_list, "epochs": 16},
    )
    assert train_resp.status_code == 200

    predict_resp = client.post(
        "/api/dl/anomaly/predict",
        json={
            "model_name": "gan",
            "coords": coords_list,
            "values": values_list,
            "threshold_method": "percentile",
            "percentile": 92.0,
            "k": 2.4,
        },
    )
    assert predict_resp.status_code == 200
    predict_json = predict_resp.json()
    assert predict_json["model_name"] == "gan"
    assert "prediction" in predict_json
    assert "anomaly_indices" in predict_json["prediction"]
    assert "anomaly_scores" in predict_json["prediction"]
    assert "score_components" in predict_json["prediction"]
    assert "score_preview" in predict_json

    explain_resp = client.post(
        "/api/dl/anomaly/explain",
        json={
            "model_name": "gan",
            "coords": coords_list,
            "values": values_list,
            "method": "hybrid",
            "top_k": 4,
            "max_explain_nodes": 6,
            "num_samples": 160,
            "nsamples": 100,
            "include_prediction": True,
        },
    )
    assert explain_resp.status_code == 200
    explain_json = explain_resp.json()
    assert explain_json["model_name"] == "gan"
    assert "lime" in explain_json
    assert "shap" in explain_json
    assert "generator_analysis" in explain_json["lime"]
    assert "discriminator_analysis" in explain_json["lime"]

    async def _run_async_checks() -> None:
        service = DeepLearningService()
        await asyncio.gather(
            asyncio.to_thread(service.predict_anomaly, "gan", coords_list, values_list, "percentile", 91.0, 2.1),
            asyncio.to_thread(
                service.explain_anomaly,
                model_name="gan",
                coords=coords_list,
                values=values_list,
                method="hybrid",
                top_k=4,
                include_prediction=True,
                num_samples=150,
                nsamples=90,
                max_explain_nodes=6,
            ),
            asyncio.to_thread(
                service.detect_realtime_anomaly,
                "gan",
                [{"coords": coords_list[:64], "values": values_list[:64]}, {"coords": coords_list[64:], "values": values_list[64:]}],
                "adaptive",
                95.0,
                2.1,
            ),
        )

    asyncio.run(_run_async_checks())


def test_gan_lime_stage4_performance_fields() -> None:
    coords, values, _ = _make_data()
    model = GANAnomalyDetector()
    model.fit(coords, values)

    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=2, lime_num_samples=320))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=8, num_samples=300)

    perf = out["performance"]
    assert perf["cache_hit"] is False
    assert perf["parallel_workers"] >= 1
    assert perf["post_parallel_workers"] >= 1
    assert perf["lime_sampling_budget"] <= 300
    assert 1 <= perf["lime_training_size"] <= len(values)
    assert perf["memory_bytes"] > 0


def test_gan_shap_stage4_reduction_and_cache() -> None:
    coords, values, _ = _make_data(seed=61)
    model = GANAnomalyDetector()
    model.fit(coords, values)

    adapter = GANAnomalySHAPAdapter(config=GANExplanationConfig(parallel_workers=2, shap_nsamples=220, shap_feature_cap=6))
    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=7, nsamples=220)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=7, nsamples=220)

    perf = out1["performance"]
    assert perf["effective_feature_count"] <= 6
    assert 0.0 < perf["feature_reduction_ratio"] <= 1.0
    assert perf["memory_bytes"] > 0
    assert out2["performance"]["cache_hit"] is True
