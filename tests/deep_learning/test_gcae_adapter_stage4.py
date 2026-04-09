from __future__ import annotations

import asyncio

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from deep_learning.models.anomaly_detection import GCAEAnomalyDetector
from services.backend.app.dl_services.api import router
from services.backend.app.dl_services.service import DeepLearningService


def _make_data(n: int = 96, seed: int = 203) -> tuple[np.ndarray, np.ndarray, set[int]]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.2) + np.cos(coords[:, 1] * 3.8) + rng.normal(0.0, 0.05, size=n)
    injected = {8, 27, 53, 81}
    for idx in injected:
        values[idx] += 1.35
    return coords, values, injected


def test_gcae_end_to_end_detection_explain_graph_processing_and_accuracy() -> None:
    coords, values, injected = _make_data()
    service = DeepLearningService()

    train_out = service.train_anomaly_model("gcae", coords.tolist(), values.tolist(), epochs=16)
    predict_out = service.predict_anomaly(
        "gcae",
        coords.tolist(),
        values.tolist(),
        threshold_method="percentile",
        percentile=90.0,
        k=2.3,
    )
    explain_out = service.explain_anomaly(
        model_name="gcae",
        coords=coords.tolist(),
        values=values.tolist(),
        method="hybrid",
        top_k=5,
        max_explain_nodes=6,
        include_prediction=True,
        num_samples=140,
        nsamples=100,
    )

    assert train_out["model_name"] == "gcae"
    assert train_out["training"]["graph_nodes"] == len(values)
    assert predict_out["model_name"] == "gcae"
    assert "prediction" in predict_out
    assert "score_preview" in predict_out
    assert explain_out["summary"]["method"] == "hybrid"
    assert "lime" in explain_out
    assert "shap" in explain_out
    assert "prediction" in explain_out

    model = service.anomaly_models["gcae"]
    assert isinstance(model, GCAEAnomalyDetector)
    graph_payload = model.preprocess_graph_data(coords, values, batch_size=24)
    assert graph_payload["validation"]["is_valid"] is True
    assert len(graph_payload["feature_names"]) == 11
    assert np.asarray(graph_payload["processed_features"], dtype=float).shape == (len(values), 11)
    assert np.asarray(graph_payload["adjacency_matrix"], dtype=float).shape == (len(values), len(values))
    assert len(graph_payload["batch_slices"]) >= 2

    anomaly_indices = set(int(i) for i in predict_out["prediction"]["anomaly_indices"])
    hit_count = len(injected.intersection(anomaly_indices))
    assert hit_count >= 2


def test_gcae_api_frontend_contract_and_async_integration() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    coords, values, _ = _make_data(seed=241)
    coords_list = coords.tolist()
    values_list = values.tolist()

    train_resp = client.post(
        "/api/dl/anomaly/train",
        json={"model_name": "gcae", "coords": coords_list, "values": values_list, "epochs": 14},
    )
    assert train_resp.status_code == 200

    predict_resp = client.post(
        "/api/dl/anomaly/predict",
        json={
            "model_name": "gcae",
            "coords": coords_list,
            "values": values_list,
            "threshold_method": "percentile",
            "percentile": 92.0,
            "k": 2.4,
        },
    )
    assert predict_resp.status_code == 200
    predict_json = predict_resp.json()
    assert predict_json["model_name"] == "gcae"
    assert "prediction" in predict_json
    assert "anomaly_indices" in predict_json["prediction"]
    assert "anomaly_scores" in predict_json["prediction"]
    assert "score_preview" in predict_json

    explain_resp = client.post(
        "/api/dl/anomaly/explain",
        json={
            "model_name": "gcae",
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
    assert explain_json["model_name"] == "gcae"
    assert "lime" in explain_json
    assert "shap" in explain_json

    async def _run_async_checks() -> None:
        service = DeepLearningService()
        await asyncio.gather(
            asyncio.to_thread(service.predict_anomaly, "gcae", coords_list, values_list, "percentile", 92.0, 2.2),
            asyncio.to_thread(
                service.explain_anomaly,
                model_name="gcae",
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
                "gcae",
                [{"coords": coords_list[:48], "values": values_list[:48]}, {"coords": coords_list[48:], "values": values_list[48:]}],
                "adaptive",
                95.0,
                2.1,
            ),
        )

    asyncio.run(_run_async_checks())
