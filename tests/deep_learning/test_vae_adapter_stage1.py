from __future__ import annotations

import asyncio

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from deep_learning.models.anomaly_detection import VAEAnomalyDetector
from services.backend.app.dl_services.api import router
from services.backend.app.dl_services.service import DeepLearningService
from services.backend.app.dl_services.vae_anomaly_explainer import VAEAnomalyLIMEAdapter, VAEAnomalySHAPAdapter


def _make_data(n: int = 84, seed: int = 101) -> tuple[np.ndarray, np.ndarray, set[int]]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.2) + np.cos(coords[:, 1] * 3.4) + rng.normal(0.0, 0.05, size=n)
    injected = {7, 18, 41, 66}
    for idx in injected:
        values[idx] += 1.35
    return coords, values, injected


def test_vae_end_to_end_detection_explain_and_accuracy() -> None:
    coords, values, injected = _make_data()
    service = DeepLearningService()

    train_out = service.train_anomaly_model("vae", coords.tolist(), values.tolist(), epochs=12)
    predict_out = service.predict_anomaly(
        "vae",
        coords.tolist(),
        values.tolist(),
        threshold_method="percentile",
        percentile=90.0,
        k=2.2,
    )
    explain_out = service.explain_anomaly(
        model_name="vae",
        coords=coords.tolist(),
        values=values.tolist(),
        method="hybrid",
        top_k=5,
        max_explain_nodes=6,
        include_prediction=True,
        num_samples=120,
        nsamples=90,
    )

    assert train_out["model_name"] == "vae"
    assert train_out["training"]["epochs"] >= 1
    assert predict_out["model_name"] == "vae"
    assert "prediction" in predict_out
    assert "score_preview" in predict_out
    assert explain_out["summary"]["method"] == "hybrid"
    assert "lime" in explain_out
    assert "shap" in explain_out
    assert "prediction" in explain_out

    anomaly_indices = set(int(i) for i in predict_out["prediction"]["anomaly_indices"])
    hit_count = len(injected.intersection(anomaly_indices))
    assert hit_count >= 2


def test_vae_explain_adapters_cache_and_top_feature_index_consistency() -> None:
    coords, values, _ = _make_data(seed=131)
    model = VAEAnomalyDetector()
    model.fit(coords, values)

    lime_adapter = VAEAnomalyLIMEAdapter()
    lime1 = lime_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=120)
    lime2 = lime_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=120)
    assert lime1["summary"]["method"] == "lime"
    assert lime1["performance"]["cache_hit"] is False
    assert lime2["performance"]["cache_hit"] is True

    context = lime_adapter._build_context(model=model, coords=coords, values=values)
    feature_names = context["feature_names"]
    for item in lime1["summary"]["top_features"]:
        idx = int(item["feature_index"])
        assert 0 <= idx < len(feature_names)
        assert feature_names[idx] == item["feature_name"]

    shap_adapter = VAEAnomalySHAPAdapter()
    shap1 = shap_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=90)
    shap2 = shap_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=90)
    assert shap1["summary"]["method"] == "shap"
    assert shap1["performance"]["cache_hit"] is False
    assert shap2["performance"]["cache_hit"] is True


def test_vae_api_frontend_contract_and_async_integration() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    coords, values, _ = _make_data(seed=151)
    coords_list = coords.tolist()
    values_list = values.tolist()

    train_resp = client.post(
        "/api/dl/anomaly/train",
        json={"model_name": "vae", "coords": coords_list, "values": values_list, "epochs": 10},
    )
    assert train_resp.status_code == 200

    predict_resp = client.post(
        "/api/dl/anomaly/predict",
        json={
            "model_name": "vae",
            "coords": coords_list,
            "values": values_list,
            "threshold_method": "percentile",
            "percentile": 92.0,
            "k": 2.4,
        },
    )
    assert predict_resp.status_code == 200
    predict_json = predict_resp.json()
    assert predict_json["model_name"] == "vae"
    assert "prediction" in predict_json
    assert "anomaly_indices" in predict_json["prediction"]
    assert "anomaly_scores" in predict_json["prediction"]
    assert "score_preview" in predict_json

    explain_resp = client.post(
        "/api/dl/anomaly/explain",
        json={
            "model_name": "vae",
            "coords": coords_list,
            "values": values_list,
            "method": "hybrid",
            "top_k": 4,
            "max_explain_nodes": 5,
            "num_samples": 120,
            "nsamples": 90,
            "include_prediction": True,
        },
    )
    assert explain_resp.status_code == 200
    explain_json = explain_resp.json()
    assert explain_json["model_name"] == "vae"
    assert "lime" in explain_json
    assert "shap" in explain_json

    async def _run_async_checks() -> None:
        service = DeepLearningService()
        await asyncio.gather(
            asyncio.to_thread(service.predict_anomaly, "vae", coords_list, values_list, "percentile", 92.0, 2.2),
            asyncio.to_thread(
                service.explain_anomaly,
                model_name="vae",
                coords=coords_list,
                values=values_list,
                method="hybrid",
                top_k=4,
                include_prediction=True,
                num_samples=120,
                nsamples=80,
                max_explain_nodes=5,
            ),
            asyncio.to_thread(
                service.detect_realtime_anomaly,
                "vae",
                [{"coords": coords_list[:42], "values": values_list[:42]}, {"coords": coords_list[42:], "values": values_list[42:]}],
                "adaptive",
                95.0,
                2.1,
            ),
        )

    asyncio.run(_run_async_checks())

