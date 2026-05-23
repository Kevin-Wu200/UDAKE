from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

services_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(services_root))

from backend.app.main import app


def _train_payload() -> dict:
    x = [120.1, 120.2, 120.3, 120.4, 120.5]
    y = [30.1, 30.2, 30.3, 30.4, 30.5]
    z = [10.0, 10.5, 11.0, 11.2, 11.5]
    t0 = 1711929600
    t = [t0 + i * 86400 for i in range(5)]
    value = [80.0, 83.0, 86.0, 85.0, 88.0]
    return {
        "data": {"x": x, "y": y, "z": z, "t": t, "value": value},
        "model_type": "nonseparable",
        "options": {"optimization": {"max_iterations": 20}},
    }


def test_train_contains_gpu_probe() -> None:
    with TestClient(app) as client:
        resp = client.post("/api/spatiotemporal/train", json=_train_payload())
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert "gpu_acceleration" in body
        assert "backend" in body["gpu_acceleration"]


def test_auto_select_contains_sampling_plan() -> None:
    with TestClient(app) as client:
        payload = _train_payload()
        hist = payload["data"]
        new_samples = {
            "x": [120.12, 120.22, 120.32, 120.42],
            "y": [30.12, 30.22, 30.32, 30.42],
            "z": [10.1, 10.7, 11.1, 11.4],
            "t": [1712016000, 1712102400, 1712188800, 1712275200],
            "value": [81.0, 84.0, 86.0, 87.0],
        }

        y_true = np.array(new_samples["value"], dtype=np.float64)
        prediction_results = {
            "separated": [{"predicted": float(v)} for v in (y_true + 2.5)],
            "product": [{"predicted": float(v)} for v in (y_true + 1.0)],
            "nonseparable": [{"predicted": float(v)} for v in (y_true + 0.2)],
        }

        resp = client.post(
            "/api/spatiotemporal/auto-select",
            json={
                "historical_data": hist,
                "new_samples": new_samples,
                "prediction_results": prediction_results,
                "options": {"n_samples": 2, "population_size": 20, "n_generations": 8},
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["best_model"] == "nonseparable"
        assert "sampling_plan" in body
        assert len(body["sampling_plan"]["selected_points"]) >= 1


def test_mobile_gps_spatiotemporal_predict() -> None:
    with TestClient(app) as client:
        sync_resp = client.post(
            "/api/mobile-gps/sync/batch",
            json={
                "client_id": "integration_test_client",
                "project_id": "project_st_mobile",
                "strategy": "latest-wins",
                "samples": [
                    {
                        "id": "m1",
                        "project_id": "project_st_mobile",
                        "latitude": 30.11,
                        "longitude": 120.11,
                        "altitude": 10.0,
                        "accuracy": 5.0,
                        "speed": 1.0,
                        "collected_at": 1711929600000,
                    },
                    {
                        "id": "m2",
                        "project_id": "project_st_mobile",
                        "latitude": 30.21,
                        "longitude": 120.21,
                        "altitude": 10.5,
                        "accuracy": 4.5,
                        "speed": 1.2,
                        "collected_at": 1712016000000,
                    },
                    {
                        "id": "m3",
                        "project_id": "project_st_mobile",
                        "latitude": 30.31,
                        "longitude": 120.31,
                        "altitude": 11.0,
                        "accuracy": 4.0,
                        "speed": 1.1,
                        "collected_at": 1712102400000,
                    },
                ],
            },
        )
        assert sync_resp.status_code == 200, sync_resp.text

        pred_resp = client.post(
            "/api/mobile-gps/spatiotemporal/predict",
            json={
                "project_id": "project_st_mobile",
                "target_positions": {
                    "x": [120.2, 120.25],
                    "y": [30.2, 30.25],
                    "z": [10.5, 10.8],
                },
                "target_times": [1712188800, 1712275200],
                "prediction_days": 3,
                "options": {"model_type": "separated", "use_cache": False},
            },
        )
        assert pred_resp.status_code == 200, pred_resp.text
        body = pred_resp.json()["data"]
        assert body["project_id"] == "project_st_mobile"
        assert body["trained_model_id"].startswith("st_model_")
        assert body["prediction"]["summary"]["total_predictions"] == 4
