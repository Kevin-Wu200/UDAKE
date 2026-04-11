from __future__ import annotations

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backend.app.dl_services.api import router
from services.backend.app.dl_services.service import DeepLearningService


def _spatial_samples() -> list[list[float]]:
    return [
        [0.10, 0.10, 1.20],
        [0.20, 0.15, 1.35],
        [0.35, 0.40, 1.10],
        [0.55, 0.60, 0.75],
        [0.75, 0.20, 1.60],
        [0.80, 0.75, 0.50],
    ]


def _uncertainty_map(size: int = 12) -> list[list[float]]:
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    arr = np.clip(0.45 + 0.25 * np.sin(xx * 3.0) + 0.2 * np.cos(yy * 4.0), 0.01, 1.0)
    return arr.tolist()


def _spatiotemporal_coords(n_nodes: int = 10) -> list[list[float]]:
    x = np.linspace(0.0, 1.0, n_nodes)
    y = np.linspace(0.1, 0.9, n_nodes)
    return [[float(a), float(b)] for a, b in zip(x, y)]


def _spatiotemporal_series(n_nodes: int = 10, seq_len: int = 18, n_features: int = 2) -> list[list[list[float]]]:
    t = np.linspace(0.0, 2.0 * np.pi, seq_len)
    series: list[list[list[float]]] = []
    for i in range(n_nodes):
        phase = 0.3 * i
        val = np.sin(t + phase) + 0.2 * np.cos(2.0 * t + phase)
        node: list[list[float]] = []
        for j in range(seq_len):
            feat = [float(val[j])]
            if n_features > 1:
                feat.append(float(np.cos(t[j] + phase)))
            for _ in range(2, n_features):
                feat.append(float(val[j]))
            node.append(feat)
        series.append(node)
    return series


def _fusion_models() -> list[dict[str, object]]:
    return [
        {
            "model_id": "m1",
            "model_name": "gnn_kriging",
            "predictions": [1.0, 1.2, 1.1, 1.3, 1.25, 1.35],
            "variances": [0.05, 0.05, 0.06, 0.05, 0.05, 0.06],
        },
        {
            "model_id": "m2",
            "model_name": "attention_kriging",
            "predictions": [0.95, 1.25, 1.05, 1.28, 1.2, 1.33],
            "variances": [0.07, 0.06, 0.07, 0.07, 0.08, 0.07],
        },
        {
            "model_id": "m3",
            "model_name": "residual_kriging",
            "predictions": [1.05, 1.18, 1.12, 1.27, 1.22, 1.31],
            "variances": [0.06, 0.06, 0.06, 0.06, 0.06, 0.06],
        },
    ]


def _fusion_true_values() -> list[float]:
    return [1.0, 1.2, 1.1, 1.3, 1.24, 1.34]


def test_service_core() -> None:
    service = DeepLearningService()
    health = service.health()
    assert health["status"] == "healthy"
    assert "dummy_regressor" in health["registered_models"]
    assert "gnn_kriging" in health["registered_models"]
    assert "trained_spatiotemporal_models" in health

    train = service.train_demo_model([[0.1, 1.0], [0.2, 0.9]])
    assert train["training"]["epochs_ran"] >= 1

    pred = service.predict([[1.0, 2.0], [3.0, 4.0]], bias=0.5)
    assert pred["predictions"] == [0.5, 0.5]


def test_service_spatial_train_and_predict() -> None:
    service = DeepLearningService()
    samples = _spatial_samples()

    train = service.train_spatial_model(model_type="gnn", samples=samples, epochs=6)
    assert train["model_type"] == "gnn"
    assert train["training"]["epochs_ran"] >= 1

    pred = service.predict_spatial(
        model_type="gnn",
        samples=samples,
        queries=[[0.15, 0.12], [0.6, 0.5]],
        blend_ratio=0.6,
    )
    assert pred["model_type"] == "gnn"
    assert len(pred["prediction"]) == 2
    assert len(pred["variance"]) == 2


def test_api_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    health_resp = client.get("/api/dl/health")
    assert health_resp.status_code == 200

    predict_resp = client.post(
        "/api/dl/predict",
        json={"samples": [[1.0, 2.0], [2.0, 2.0]], "bias": 1.2},
    )
    assert predict_resp.status_code == 200
    assert predict_resp.json()["predictions"] == [1.2, 1.2]


def test_api_spatial_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    samples = _spatial_samples()

    train_resp = client.post(
        "/api/dl/spatial/train",
        json={"model_type": "residual", "samples": samples, "epochs": 5},
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["model_type"] == "residual"

    pred_resp = client.post(
        "/api/dl/spatial/predict",
        json={
            "model_type": "attention",
            "samples": samples,
            "queries": [[0.1, 0.1], [0.5, 0.5], [0.8, 0.8]],
            "blend_ratio": 0.7,
        },
    )
    assert pred_resp.status_code == 200
    payload = pred_resp.json()
    assert len(payload["prediction"]) == 3
    assert len(payload["variance"]) == 3


def test_service_sampling_rl_train_and_recommend() -> None:
    service = DeepLearningService()
    uncertainty = _uncertainty_map(size=10)

    train = service.train_sampling_rl(
        model_name="ppo",
        uncertainty_map=uncertainty,
        existing_points=[[0.1, 0.1], [0.8, 0.7]],
        episodes=8,
        budget=12,
    )
    assert train["model_name"] == "ppo"
    assert train["training"]["summary"]["episodes"] >= 1

    rec = service.recommend_sampling_rl(
        model_name="ppo",
        uncertainty_map=uncertainty,
        existing_points=[[0.1, 0.1], [0.8, 0.7]],
        n_recommendations=6,
        fusion_strategy="hybrid",
        realtime=True,
    )
    assert rec["model_name"] == "ppo"
    assert len(rec["recommendation"]["recommendations"]) >= 1
    assert "explanations" in rec["recommendation"]
    assert "policy_decision" in rec["recommendation"]["explanations"]
    assert "action_value_visualization" in rec["recommendation"]["explanations"]
    assert "sampling_point_recommendation" in rec["recommendation"]["explanations"]
    assert "sampling_density_analysis" in rec["recommendation"]["explanations"]
    assert "sampling_region_visualization" in rec["recommendation"]["explanations"]
    assert "sampling_effect_evaluation" in rec["recommendation"]["explanations"]
    assert "sampling_optimization_suggestions" in rec["recommendation"]["explanations"]
    assert "optimization" in rec


def test_api_sampling_rl_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    uncertainty = _uncertainty_map(size=10)

    train_resp = client.post(
        "/api/dl/sampling-rl/train",
        json={
            "model_name": "dqn",
            "uncertainty_map": uncertainty,
            "existing_points": [[0.2, 0.2], [0.7, 0.6]],
            "episodes": 8,
            "budget": 12,
        },
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["model_name"] == "dqn"

    rec_resp = client.post(
        "/api/dl/sampling-rl/recommend",
        json={
            "model_name": "dqn",
            "uncertainty_map": uncertainty,
            "existing_points": [[0.2, 0.2], [0.7, 0.6]],
            "n_recommendations": 5,
            "fusion_strategy": "hybrid",
            "realtime": True,
        },
    )
    assert rec_resp.status_code == 200
    payload = rec_resp.json()
    assert payload["model_name"] == "dqn"
    assert len(payload["recommendation"]["recommendations"]) >= 1
    assert "explanations" in payload["recommendation"]
    assert "policy_decision" in payload["recommendation"]["explanations"]


def test_service_sampling_rl_train_and_recommend_a2c() -> None:
    service = DeepLearningService()
    uncertainty = _uncertainty_map(size=10)

    train = service.train_sampling_rl(
        model_name="a2c",
        uncertainty_map=uncertainty,
        existing_points=[[0.12, 0.16], [0.72, 0.64]],
        episodes=8,
        budget=12,
    )
    assert train["model_name"] == "a2c"
    assert train["training"]["summary"]["episodes"] >= 1

    rec = service.recommend_sampling_rl(
        model_name="a2c",
        uncertainty_map=uncertainty,
        existing_points=[[0.12, 0.16], [0.72, 0.64]],
        n_recommendations=6,
        fusion_strategy="hybrid",
        realtime=True,
    )
    assert rec["model_name"] == "a2c"
    assert len(rec["recommendation"]["recommendations"]) >= 1
    assert "explanations" in rec["recommendation"]
    assert "policy_decision" in rec["recommendation"]["explanations"]
    assert "optimization" in rec


def test_api_sampling_rl_routes_a2c() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    uncertainty = _uncertainty_map(size=10)

    train_resp = client.post(
        "/api/dl/sampling-rl/train",
        json={
            "model_name": "a2c",
            "uncertainty_map": uncertainty,
            "existing_points": [[0.18, 0.22], [0.66, 0.58]],
            "episodes": 8,
            "budget": 12,
        },
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["model_name"] == "a2c"

    rec_resp = client.post(
        "/api/dl/sampling-rl/recommend",
        json={
            "model_name": "a2c",
            "uncertainty_map": uncertainty,
            "existing_points": [[0.18, 0.22], [0.66, 0.58]],
            "n_recommendations": 5,
            "fusion_strategy": "hybrid",
            "realtime": True,
        },
    )
    assert rec_resp.status_code == 200
    payload = rec_resp.json()
    assert payload["model_name"] == "a2c"
    assert len(payload["recommendation"]["recommendations"]) >= 1
    assert "explanations" in payload["recommendation"]
    assert "policy_decision" in payload["recommendation"]["explanations"]


def test_service_spatiotemporal_train_predict_and_online_update() -> None:
    service = DeepLearningService()
    coords = _spatiotemporal_coords(10)
    series = _spatiotemporal_series(10, seq_len=20, n_features=2)
    horizon = 4
    targets = np.asarray(series, dtype=float)[:, -horizon:, 0].tolist()

    train = service.train_spatiotemporal_model(
        model_type="st_transformer",
        coords=coords,
        series=series,
        targets=targets,
        epochs=8,
        pred_horizon=horizon,
    )
    assert train["model_type"] == "st_transformer"
    assert train["training"]["epochs_ran"] >= 1

    pred = service.predict_spatiotemporal(
        model_type="st_transformer",
        coords=coords,
        series=series,
        pred_horizon=horizon,
        fusion_strategy="gating",
        targets=targets,
    )
    assert pred["model_type"] == "st_transformer"
    assert len(pred["prediction"]) == len(coords)
    assert len(pred["prediction"][0]) == horizon

    long_series = _spatiotemporal_series(10, seq_len=26, n_features=2)
    online = service.update_spatiotemporal_online(
        model_type="st_transformer",
        coords=coords,
        long_series=long_series,
        window_size=18,
        pred_horizon=horizon,
        update_interval=1,
        strategy="light",
    )
    assert online["model_type"] == "st_transformer"
    assert online["online"]["online_update"]["updated_steps"] >= 1


def test_api_spatiotemporal_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    coords = _spatiotemporal_coords(8)
    series = _spatiotemporal_series(8, seq_len=18, n_features=2)
    targets = np.asarray(series, dtype=float)[:, -3:, 0].tolist()

    train_resp = client.post(
        "/api/dl/spatiotemporal/train",
        json={
            "model_type": "gcn_lstm",
            "coords": coords,
            "series": series,
            "targets": targets,
            "epochs": 8,
            "pred_horizon": 3,
        },
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["model_type"] == "gcn_lstm"

    pred_resp = client.post(
        "/api/dl/spatiotemporal/predict",
        json={
            "model_type": "gcn_lstm",
            "coords": coords,
            "series": series,
            "pred_horizon": 3,
            "fusion_strategy": "gating",
            "targets": targets,
        },
    )
    assert pred_resp.status_code == 200
    pred_payload = pred_resp.json()
    assert pred_payload["model_type"] == "gcn_lstm"
    assert len(pred_payload["prediction"]) == len(coords)

    long_series = _spatiotemporal_series(8, seq_len=24, n_features=2)
    online_resp = client.post(
        "/api/dl/spatiotemporal/online-update",
        json={
            "model_type": "gcn_lstm",
            "coords": coords,
            "long_series": long_series,
            "window_size": 16,
            "pred_horizon": 3,
            "update_interval": 1,
            "strategy": "light",
        },
    )
    assert online_resp.status_code == 200
    online_payload = online_resp.json()
    assert online_payload["model_type"] == "gcn_lstm"
    assert online_payload["online"]["online_update"]["updated_steps"] >= 1


def test_service_fusion_workflow() -> None:
    service = DeepLearningService()
    models = _fusion_models()
    true_values = _fusion_true_values()

    train = service.train_fusion_profile(
        profile_id="demo_profile",
        models=models,
        true_values=true_values,
        strategy="dynamic",
        weight_method="adaptive",
        adaptive_mode="attention",
        context={"difficulty": [1.0] * len(true_values)},
    )
    assert train["profile"]["profile_id"] == "demo_profile"
    assert "rmse" in train["result"]["metrics"]

    infer = service.predict_fusion(
        models=models,
        profile_id="demo_profile",
        true_values=true_values,
        context={"difficulty": [0.9] * len(true_values)},
    )
    assert len(infer["result"]["fused_predictions"]) == len(true_values)
    assert infer["selected_strategy"] in {
        "dynamic",
        "stacking",
        "variance_weighted",
        "median",
        "weighted_average",
    }

    compare = service.compare_fusion_strategies(models=models, true_values=true_values)
    assert "weighted_average" in compare
    assert "dynamic" in compare

    optimize = service.optimize_fusion_weights(models=models, true_values=true_values, strategy="weighted_average")
    assert optimize["best_method"] is not None

    hybrid = service.hybrid_fusion(
        kriging_prediction=[1.0, 1.2, 1.1],
        deep_prediction=[0.98, 1.23, 1.12],
        mode="residual",
        ratio=0.65,
    )
    assert len(hybrid["prediction"]) == 3

    multimodal = service.multimodal_fusion(
        modalities=[[1.0, 1.2, 1.1], [0.9, 1.3, 1.0], [1.1, 1.1, 1.2]],
        strategy="hybrid",
        weights=[0.4, 0.3, 0.3],
    )
    assert len(multimodal["fused"]) == 3

    selected = service.select_fusion_model(
        performance_scores={"gnn": 0.12, "attention": 0.1},
        uncertainty_scores={"gnn": 0.2, "attention": 0.08},
        input_score=0.8,
    )
    assert selected["selected_model"] in {"gnn", "attention"}

    monitor = service.fusion_monitor_status()
    assert monitor["requests"]["total"] >= 4

    registry = service.fusion_registry_status()
    assert "demo_profile" in registry["profiles"]

    access_ok = service.fusion_check_access(token="internal-token", client_id="ut-fusion")
    access_fail = service.fusion_check_access(token="bad-token", client_id="ut-fusion")
    assert access_ok["ok"] is True
    assert access_fail["ok"] is False


def test_api_fusion_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    models = _fusion_models()
    true_values = _fusion_true_values()

    train_resp = client.post(
        "/api/dl/fusion/train-profile",
        json={
            "profile_id": "api_profile",
            "models": models,
            "true_values": true_values,
            "strategy": "dynamic",
            "weight_method": "adaptive",
            "adaptive_mode": "neural",
            "context": {"difficulty": [1.0] * len(true_values)},
        },
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["profile"]["profile_id"] == "api_profile"

    pred_resp = client.post(
        "/api/dl/fusion/predict",
        json={
            "models": models,
            "profile_id": "api_profile",
            "true_values": true_values,
            "context": {"difficulty": [0.9] * len(true_values)},
        },
    )
    assert pred_resp.status_code == 200
    pred_payload = pred_resp.json()
    assert len(pred_payload["result"]["fused_predictions"]) == len(true_values)

    compare_resp = client.post(
        "/api/dl/fusion/compare",
        json={"models": models, "true_values": true_values},
    )
    assert compare_resp.status_code == 200
    assert "weighted_average" in compare_resp.json()

    optimize_resp = client.post(
        "/api/dl/fusion/optimize",
        json={"models": models, "true_values": true_values, "strategy": "weighted_average"},
    )
    assert optimize_resp.status_code == 200
    assert optimize_resp.json()["best_method"] is not None

    hybrid_resp = client.post(
        "/api/dl/fusion/hybrid",
        json={
            "kriging_prediction": [1.0, 1.2, 1.1],
            "deep_prediction": [0.98, 1.23, 1.12],
            "mode": "feature",
            "ratio": 0.55,
        },
    )
    assert hybrid_resp.status_code == 200
    assert len(hybrid_resp.json()["prediction"]) == 3

    multimodal_resp = client.post(
        "/api/dl/fusion/multimodal",
        json={
            "modalities": [[1.0, 1.2], [0.9, 1.3], [1.1, 1.1]],
            "strategy": "decision_level",
            "weights": [0.5, 0.25, 0.25],
        },
    )
    assert multimodal_resp.status_code == 200
    assert len(multimodal_resp.json()["fused"]) == 2

    select_resp = client.post(
        "/api/dl/fusion/select-model",
        json={
            "performance_scores": {"gnn": 0.2, "attention": 0.1},
            "uncertainty_scores": {"gnn": 0.25, "attention": 0.09},
            "input_score": 0.85,
        },
    )
    assert select_resp.status_code == 200
    assert select_resp.json()["selected_model"] in {"gnn", "attention"}

    monitor_resp = client.get("/api/dl/fusion/monitor")
    assert monitor_resp.status_code == 200
    assert monitor_resp.json()["requests"]["total"] >= 1

    registry_resp = client.get("/api/dl/fusion/registry")
    assert registry_resp.status_code == 200
    assert "profiles" in registry_resp.json()

    access_ok_resp = client.post("/api/dl/fusion/access", json={"token": "internal-token", "client_id": "api-fusion"})
    access_fail_resp = client.post("/api/dl/fusion/access", json={"token": "wrong-token", "client_id": "api-fusion"})
    assert access_ok_resp.status_code == 200
    assert access_fail_resp.status_code == 200
    assert access_ok_resp.json()["ok"] is True
    assert access_fail_resp.json()["ok"] is False
