from __future__ import annotations

import asyncio

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from deep_learning.models.anomaly_detection import ContrastiveAnomalyDetector
from services.backend.app.dl_services.api import router
from services.backend.app.dl_services.contrastive_anomaly_explainer import (
    ContrastiveExplanationConfig,
    ContrastiveLimeAdapter,
    ContrastiveShapAdapter,
)
from services.backend.app.dl_services.service import DeepLearningService


def _make_data(n: int = 128, seed: int = 47) -> tuple[np.ndarray, np.ndarray, set[int]]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.2) + np.cos(coords[:, 1] * 4.6) + rng.normal(0.0, 0.05, size=n)
    injected = {6, 29, 61, 95}
    for idx in injected:
        values[idx] += 1.20
    values[5::23] -= 0.75
    return coords, values, injected


def test_contrastive_end_to_end_detection_explain_pipeline_and_accuracy() -> None:
    coords, values, injected = _make_data()
    service = DeepLearningService()

    train_out = service.train_anomaly_model("contrastive", coords.tolist(), values.tolist(), epochs=18)
    predict_out = service.predict_anomaly(
        "contrastive",
        coords.tolist(),
        values.tolist(),
        threshold_method="percentile",
        percentile=90.0,
        k=2.3,
    )
    explain_out = service.explain_anomaly(
        model_name="contrastive",
        coords=coords.tolist(),
        values=values.tolist(),
        method="hybrid",
        top_k=5,
        max_explain_nodes=7,
        include_prediction=True,
        num_samples=180,
        nsamples=120,
    )

    assert train_out["model_name"] == "contrastive"
    assert train_out["training"]["feature_bank_size"] >= 1
    assert predict_out["model_name"] == "contrastive"
    assert "prediction" in predict_out
    assert "score_preview" in predict_out

    prediction = predict_out["prediction"]
    assert "anomaly_indices" in prediction
    assert "anomaly_scores" in prediction
    assert "score_components" in prediction
    assert prediction["online_feature_bank_size"] >= 1

    components = prediction["score_components"]
    assert "feature_distance" in components
    assert "density" in components
    assert "nearest_neighbor" in components
    assert "bank_similarity" in components
    assert len(components["feature_distance"]) == len(values)
    assert len(components["density"]) == len(values)
    assert len(components["nearest_neighbor"]) == len(values)
    assert len(components["bank_similarity"]) == len(values)

    assert explain_out["summary"]["method"] == "hybrid"
    assert "lime" in explain_out
    assert "shap" in explain_out
    assert "prediction" in explain_out
    assert "embedding_analysis" in explain_out["lime"]
    assert "similarity_distribution_analysis" in explain_out["lime"]["embedding_analysis"]
    assert "embedding_analysis" in explain_out["shap"]
    assert "similarity_distribution_analysis" in explain_out["shap"]["embedding_analysis"]

    model = service.anomaly_models["contrastive"]
    assert isinstance(model, ContrastiveAnomalyDetector)
    prep = model.preprocess_contrastive_data(coords, values, batch_size=24, use_training_stats=True, augmentation=False)
    assert prep["validation"]["is_valid"] is True
    assert len(prep["feature_names"]) == 10
    assert np.asarray(prep["processed_features"], dtype=float).shape == (len(values), 10)
    assert len(prep["positive_pairs"]) == len(values)
    assert len(prep["negative_pairs"]) == len(values)
    assert len(prep["batch_slices"]) >= 2

    emb = np.asarray(model.encode(coords, values), dtype=float)
    assert emb.shape[0] == len(values)
    assert emb.shape[1] > 0

    scores = np.asarray(prediction["anomaly_scores"], dtype=float)
    injected_scores = np.asarray([scores[idx] for idx in sorted(injected)], dtype=float)
    normal_indices = [idx for idx in range(len(scores)) if idx not in injected]
    normal_scores = np.asarray([scores[idx] for idx in normal_indices], dtype=float)
    assert injected_scores.mean() > normal_scores.mean()


def test_contrastive_api_frontend_contract_and_async_integration() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    coords, values, _ = _make_data(seed=59)
    coords_list = coords.tolist()
    values_list = values.tolist()

    train_resp = client.post(
        "/api/dl/anomaly/train",
        json={"model_name": "contrastive", "coords": coords_list, "values": values_list, "epochs": 16},
    )
    assert train_resp.status_code == 200

    predict_resp = client.post(
        "/api/dl/anomaly/predict",
        json={
            "model_name": "contrastive",
            "coords": coords_list,
            "values": values_list,
            "threshold_method": "percentile",
            "percentile": 92.0,
            "k": 2.4,
        },
    )
    assert predict_resp.status_code == 200
    predict_json = predict_resp.json()
    assert predict_json["model_name"] == "contrastive"
    assert "prediction" in predict_json
    assert "anomaly_indices" in predict_json["prediction"]
    assert "anomaly_scores" in predict_json["prediction"]
    assert "score_components" in predict_json["prediction"]
    assert "score_preview" in predict_json

    explain_resp = client.post(
        "/api/dl/anomaly/explain",
        json={
            "model_name": "contrastive",
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
    assert explain_json["model_name"] == "contrastive"
    assert "lime" in explain_json
    assert "shap" in explain_json
    assert "embedding_analysis" in explain_json["lime"]
    assert "embedding_analysis" in explain_json["shap"]

    async def _run_async_checks() -> None:
        service = DeepLearningService()
        await asyncio.gather(
            asyncio.to_thread(service.predict_anomaly, "contrastive", coords_list, values_list, "percentile", 91.0, 2.1),
            asyncio.to_thread(
                service.explain_anomaly,
                model_name="contrastive",
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
                "contrastive",
                [{"coords": coords_list[:64], "values": values_list[:64]}, {"coords": coords_list[64:], "values": values_list[64:]}],
                "adaptive",
                95.0,
                2.1,
            ),
        )

    asyncio.run(_run_async_checks())


def test_contrastive_lime_stage4_performance_fields() -> None:
    coords, values, _ = _make_data()
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=16)

    adapter = ContrastiveLimeAdapter(config=ContrastiveExplanationConfig(parallel_workers=2, lime_num_samples=320))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=8, num_samples=300)

    perf = out["performance"]
    assert perf["cache_hit"] is False
    assert perf["parallel_workers"] >= 1
    assert perf["post_parallel_workers"] >= 1
    assert perf["lime_sampling_budget"] <= 300
    assert 1 <= perf["lime_training_size"] <= len(values)
    assert perf["memory_bytes"] > 0


def test_contrastive_shap_stage4_reduction_and_cache() -> None:
    coords, values, _ = _make_data(seed=61)
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=16)

    adapter = ContrastiveShapAdapter(config=ContrastiveExplanationConfig(parallel_workers=2, shap_nsamples=220, shap_feature_cap=6))
    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=7, nsamples=220)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=7, nsamples=220)

    perf = out1["performance"]
    assert perf["effective_feature_count"] <= 6
    assert 0.0 < perf["feature_reduction_ratio"] <= 1.0
    assert perf["memory_bytes"] > 0
    assert out2["performance"]["cache_hit"] is True
