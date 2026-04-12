from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backend.app.dl_services.api import router


def _models() -> list[dict]:
    return [
        {
            "model_id": "m1",
            "predictions": [10.0, 10.8, 11.1, 11.3, 10.9, 11.0],
            "variances": [0.09, 0.09, 0.08, 0.08, 0.1, 0.1],
        },
        {
            "model_id": "m2",
            "predictions": [10.2, 10.6, 11.0, 11.4, 11.1, 11.2],
            "variances": [0.06, 0.07, 0.07, 0.08, 0.08, 0.09],
        },
        {
            "model_id": "m3",
            "predictions": [10.1, 10.7, 11.2, 11.2, 11.0, 11.1],
            "variances": [0.07, 0.08, 0.09, 0.07, 0.09, 0.1],
        },
    ]


def _true_values() -> list[float]:
    return [10.1, 10.7, 11.1, 11.25, 11.0, 11.05]


def test_fusion_api_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    train_resp = client.post(
        "/api/dl/fusion/train-profile",
        json={
            "profile_id": "api_profile",
            "models": _models(),
            "true_values": _true_values(),
            "strategy": "dynamic",
            "weight_method": "adaptive",
            "adaptive_mode": "neural",
        },
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["profile"]["profile_id"] == "api_profile"

    pred_resp = client.post(
        "/api/dl/fusion/predict",
        json={
            "models": _models(),
            "profile_id": "api_profile",
            "true_values": _true_values(),
        },
    )
    assert pred_resp.status_code == 200
    assert len(pred_resp.json()["result"]["fused_predictions"]) == len(_true_values())

    compare_resp = client.post(
        "/api/dl/fusion/compare",
        json={"models": _models(), "true_values": _true_values()},
    )
    assert compare_resp.status_code == 200
    compare_payload = compare_resp.json()
    assert "weighted_average" in compare_payload

    analysis_resp = client.post(
        "/api/dl/fusion/strategy-analysis",
        json={"models": _models(), "true_values": _true_values()},
    )
    assert analysis_resp.status_code == 200
    analysis_payload = analysis_resp.json()
    assert "strategies" in analysis_payload
    assert "analysis" in analysis_payload
    assert analysis_payload["analysis"]["best_strategy"] in analysis_payload["strategies"]

    recommend_resp = client.post(
        "/api/dl/fusion/strategy-recommend",
        json={
            "models": _models(),
            "true_values": _true_values(),
            "objective": "rmse",
        },
    )
    assert recommend_resp.status_code == 200
    recommend_payload = recommend_resp.json()
    assert recommend_payload["objective"] == "rmse"
    assert recommend_payload["recommended_strategy"] in analysis_payload["strategies"]
    assert len(recommend_payload["candidates"]) >= 1

    effectiveness_resp = client.post(
        "/api/dl/fusion/strategy-effectiveness",
        json={
            "models": _models(),
            "strategy": "dynamic",
            "true_values": _true_values(),
            "baseline_strategy": "weighted_average",
        },
    )
    assert effectiveness_resp.status_code == 200
    effectiveness_payload = effectiveness_resp.json()
    assert effectiveness_payload["target_strategy"] == "dynamic"
    assert effectiveness_payload["baseline_strategy"] == "weighted_average"
    assert "effectiveness" in effectiveness_payload

    feature_resp = client.post(
        "/api/dl/fusion/feature-analysis",
        json={
            "models": _models(),
            "true_values": _true_values(),
            "strategy": "dynamic",
            "weight_method": "adaptive",
            "context": {"difficulty": [1.0] * len(_true_values())},
        },
    )
    assert feature_resp.status_code == 200
    feature_payload = feature_resp.json()
    assert "analysis" in feature_payload
    assert feature_payload["analysis"]["basic_features"]["model_count"] == len(_models())
    assert "feature_mapping" in feature_payload["analysis"]

    optimize_resp = client.post(
        "/api/dl/fusion/optimize",
        json={"models": _models(), "true_values": _true_values(), "strategy": "weighted_average"},
    )
    assert optimize_resp.status_code == 200
    assert optimize_resp.json()["best_method"] is not None

    explain_resp = client.post(
        "/api/dl/fusion/explain",
        json={
            "models": _models(),
            "method": "hybrid",
            "top_k": 3,
            "max_explain_nodes": 4,
            "true_values": _true_values(),
            "strategy": "dynamic",
            "weight_method": "adaptive",
        },
    )
    assert explain_resp.status_code == 200
    explain_payload = explain_resp.json()
    assert explain_payload["summary"]["method"] == "hybrid"
    assert "lime" in explain_payload
    assert "shap" in explain_payload
    assert "prediction" in explain_payload

    hybrid_resp = client.post(
        "/api/dl/fusion/hybrid",
        json={
            "kriging_prediction": [1.0, 2.0, 3.0],
            "deep_prediction": [1.2, 1.9, 3.1],
            "mode": "residual",
            "ratio": 0.6,
        },
    )
    assert hybrid_resp.status_code == 200
    assert len(hybrid_resp.json()["prediction"]) == 3

    multimodal_resp = client.post(
        "/api/dl/fusion/multimodal",
        json={
            "modalities": [[1.0, 2.0], [1.1, 2.1], [0.9, 2.2]],
            "strategy": "hybrid",
        },
    )
    assert multimodal_resp.status_code == 200
    assert len(multimodal_resp.json()["fused"]) == 2

    select_resp = client.post(
        "/api/dl/fusion/select-model",
        json={
            "performance_scores": {"kriging": 0.12, "deep_learning": 0.08},
            "uncertainty_scores": {"kriging": 0.03, "deep_learning": 0.04},
            "input_score": 0.4,
        },
    )
    assert select_resp.status_code == 200
    assert "selected_model" in select_resp.json()

    monitor_resp = client.get("/api/dl/fusion/monitor")
    assert monitor_resp.status_code == 200
    assert "requests" in monitor_resp.json()

    registry_resp = client.get("/api/dl/fusion/registry")
    assert registry_resp.status_code == 200
    assert "profiles" in registry_resp.json()

    access_resp = client.post(
        "/api/dl/fusion/access",
        json={"token": "internal-token", "client_id": "api-test"},
    )
    assert access_resp.status_code == 200
    assert access_resp.json()["ok"] is True
