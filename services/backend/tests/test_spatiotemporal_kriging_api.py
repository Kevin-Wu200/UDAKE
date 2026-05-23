from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

services_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(services_root))

from backend.app.main import app


def _train_payload(model_type: str = "nonseparable") -> dict:
    x = [120.1, 120.2, 120.3, 120.4, 120.5]
    y = [30.1, 30.2, 30.3, 30.4, 30.5]
    z = [10.0, 10.5, 11.0, 11.2, 11.5]
    t0 = 1711929600
    t = [t0 + i * 86400 for i in range(5)]
    value = [80.0, 83.0, 86.0, 85.0, 88.0]
    return {
        "data": {"x": x, "y": y, "z": z, "t": t, "value": value},
        "model_type": model_type,
        "options": {
            "spatial_block_size": 500,
            "temporal_window_size": 30,
            "low_rank": 100,
            "optimization": {"method": "mle", "max_iterations": 120},
        },
    }


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_spatiotemporal_train_api(client: TestClient) -> None:
    resp = client.post("/api/spatiotemporal/train", json=_train_payload("product"))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["success"] is True
    assert body["data"]["model_type"] == "product"
    assert body["data"]["model_id"].startswith("st_model_")
    assert "parameters" in body["data"]
    assert "variogram_charts" in body["data"]
    assert "resource" in body["data"]


def test_spatiotemporal_predict_online_offline(client: TestClient) -> None:
    train_resp = client.post("/api/spatiotemporal/train", json=_train_payload("nonseparable"))
    model_id = train_resp.json()["data"]["model_id"]

    target_positions = {
        "x": [120.15, 120.35],
        "y": [30.15, 30.35],
        "z": [10.2, 11.1],
    }
    target_times = [1712016000, 1712275200]

    online_resp = client.post(
        "/api/spatiotemporal/predict",
        json={
            "model_id": model_id,
            "target_positions": target_positions,
            "target_times": target_times,
            "prediction_days": 7,
            "options": {"include_uncertainty": True, "use_cache": True, "backend_available": True},
        },
    )
    assert online_resp.status_code == 200, online_resp.text
    online_data = online_resp.json()["data"]
    assert online_data["summary"]["mode"] == "online"
    assert online_data["summary"]["total_predictions"] == 4
    assert all("precision_decay" in row for row in online_data["predictions"])

    offline_resp = client.post(
        "/api/spatiotemporal/predict",
        json={
            "model_id": model_id,
            "target_positions": target_positions,
            "target_times": target_times,
            "prediction_days": 7,
            "options": {"backend_available": False, "online_preferred": True, "use_cache": False},
        },
    )
    assert offline_resp.status_code == 200, offline_resp.text
    offline_data = offline_resp.json()["data"]
    assert offline_data["summary"]["mode"] == "offline"
    assert all(row["method"].endswith("_offline") for row in offline_data["predictions"])


def test_spatiotemporal_auto_select_api(client: TestClient) -> None:
    payload = _train_payload("separated")
    hist = payload["data"]

    new_samples = {
        "x": [120.12, 120.22, 120.32],
        "y": [30.12, 30.22, 30.32],
        "z": [10.1, 10.7, 11.1],
        "t": [1712016000, 1712102400, 1712188800],
        "value": [81.0, 84.0, 86.0],
    }

    y_true = np.array(new_samples["value"], dtype=np.float64)
    prediction_results = {
        "separated": [{"predicted": float(v)} for v in (y_true + 2.5)],
        "product": [{"predicted": float(v)} for v in (y_true + 1.0)],
        "nonseparable": [{"predicted": float(v)} for v in (y_true + 0.3)],
    }

    resp = client.post(
        "/api/spatiotemporal/auto-select",
        json={
            "historical_data": hist,
            "new_samples": new_samples,
            "prediction_results": prediction_results,
            "options": {"weight_rmse": 0.4, "weight_mae": 0.3, "weight_crps": 0.3},
        },
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["success"] is True
    assert body["data"]["best_model"] == "nonseparable"
    assert set(body["data"]["evaluation"].keys()) == {"separated", "product", "nonseparable"}


def test_spatiotemporal_incremental_update_api(client: TestClient) -> None:
    train_resp = client.post("/api/spatiotemporal/train", json=_train_payload("separated"))
    model_id = train_resp.json()["data"]["model_id"]

    resp = client.post(
        "/api/spatiotemporal/incremental-update",
        json={
            "model_id": model_id,
            "new_data": {
                "x": [120.6, 120.7, 120.8],
                "y": [30.6, 30.7, 30.8],
                "z": [11.8, 12.0, 12.2],
                "t": [1712361600, 1712448000, 1712534400],
                "value": [89.0, 90.5, 91.2],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["model_id"] == model_id
    assert body["data"]["data_stats"]["total_samples"] == 8
    assert "update_report" in body["data"]


def test_spatiotemporal_update_model_api(client: TestClient) -> None:
    train_resp = client.post("/api/spatiotemporal/train", json=_train_payload("separated"))
    model_id = train_resp.json()["data"]["model_id"]

    resp = client.post(
        "/api/spatiotemporal/update",
        json={
            "model_id": model_id,
            "new_data": {
                "x": [120.6, 120.7, 120.8],
                "y": [30.6, 30.7, 30.8],
                "z": [11.8, 12.0, 12.2],
                "t": [1712361600, 1712448000, 1712534400],
                "value": [89.0, 90.5, 91.2],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["old_model_id"] == model_id
    assert data["new_model_id"] != model_id
    assert "update_report" in data


def test_spatiotemporal_models_crud_and_evaluate_api(client: TestClient) -> None:
    train_resp = client.post("/api/spatiotemporal/train", json=_train_payload("nonseparable"))
    model_id = train_resp.json()["data"]["model_id"]

    list_resp = client.get("/api/spatiotemporal/models?page=1&page_size=10&status=active")
    assert list_resp.status_code == 200, list_resp.text
    list_data = list_resp.json()["data"]
    assert list_data["total"] >= 1
    assert any(row["model_id"] == model_id for row in list_data["models"])

    detail_resp = client.get(f"/api/spatiotemporal/models/{model_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    detail_data = detail_resp.json()["data"]
    assert detail_data["model_id"] == model_id
    assert detail_data["model_type"] == "nonseparable"

    eval_resp = client.get(f"/api/spatiotemporal/evaluate/{model_id}?metrics=rmse,mae,r2,crps")
    assert eval_resp.status_code == 200, eval_resp.text
    eval_data = eval_resp.json()["data"]
    assert set(eval_data["metrics"].keys()) == {"rmse", "mae", "r2", "crps"}
    assert "calibration" in eval_data
    assert "diagnostics" in eval_data

    del_resp = client.delete(f"/api/spatiotemporal/models/{model_id}")
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json()["data"]["model_id"] == model_id

    missing_resp = client.get(f"/api/spatiotemporal/models/{model_id}")
    assert missing_resp.status_code == 404, missing_resp.text
    missing_body = missing_resp.json()
    assert missing_body["success"] is False
    assert missing_body["error"]["code"] == "1001"
    assert "request_id" in missing_body["error"]


def test_spatiotemporal_error_response_format(client: TestClient) -> None:
    resp = client.post(
        "/api/spatiotemporal/predict",
        json={
            "model_id": "st_model_not_exists",
            "target_positions": {
                "x": [120.15],
                "y": [30.15],
                "z": [10.2],
            },
            "target_times": [1712016000],
            "prediction_days": 7,
            "options": {"include_uncertainty": True},
        },
        headers={"X-Request-ID": "req_test_custom"},
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "1001"
    assert body["error"]["request_id"] == "req_test_custom"
    assert "timestamp" in body["error"]


def test_spatiotemporal_performance_metrics_and_cache_warmup_api(client: TestClient) -> None:
    train_resp = client.post("/api/spatiotemporal/train", json=_train_payload("separated"))
    model_id = train_resp.json()["data"]["model_id"]

    warmup_resp = client.post(
        "/api/spatiotemporal/cache/warmup",
        json={
            "model_id": model_id,
            "payloads": [
                {
                    "target_positions": {
                        "x": [120.2, 120.3],
                        "y": [30.2, 30.3],
                        "z": [10.6, 10.9],
                    },
                    "target_times": [1712620800, 1712707200],
                    "prediction_days": 7,
                }
            ],
        },
    )
    assert warmup_resp.status_code == 200, warmup_resp.text
    warmup_data = warmup_resp.json()["data"]
    assert warmup_data["model_id"] == model_id
    assert warmup_data["warmed_count"] >= 0

    metrics_resp = client.get("/api/spatiotemporal/performance/metrics")
    assert metrics_resp.status_code == 200, metrics_resp.text
    metrics = metrics_resp.json()["data"]
    assert "prediction_engine" in metrics
    assert "memory" in metrics
