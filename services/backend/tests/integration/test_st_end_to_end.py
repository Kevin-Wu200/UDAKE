from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

services_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(services_root))

from backend.app.main import app


def _train_payload() -> dict:
    return {
        "data": {
            "x": [120.1, 120.2, 120.3, 120.4, 120.5, 120.6],
            "y": [30.1, 30.2, 30.3, 30.4, 30.5, 30.6],
            "z": [10.0, 10.4, 10.8, 11.2, 11.6, 12.0],
            "t": [1711929600, 1712016000, 1712102400, 1712188800, 1712275200, 1712361600],
            "value": [80.0, 81.0, 82.0, 82.6, 83.1, 83.8],
        },
        "model_type": "nonseparable",
        "options": {"optimization": {"max_iterations": 80}},
    }


def test_st_end_to_end_train_predict_update_and_cleanup() -> None:
    with TestClient(app) as client:
        train_resp = client.post("/api/spatiotemporal/train", json=_train_payload())
        assert train_resp.status_code == 200, train_resp.text
        model_id = train_resp.json()["data"]["model_id"]

        online_predict = client.post(
            "/api/spatiotemporal/predict",
            json={
                "model_id": model_id,
                "target_positions": {"x": [120.15, 120.45], "y": [30.15, 30.45], "z": [10.2, 11.3]},
                "target_times": [1712448000, 1712534400],
                "prediction_days": 7,
                "options": {"backend_available": True, "online_preferred": True, "use_cache": True},
            },
        )
        assert online_predict.status_code == 200, online_predict.text
        online_data = online_predict.json()["data"]
        assert online_data["summary"]["mode"] == "online"
        assert online_data["summary"]["total_predictions"] == 4

        offline_predict = client.post(
            "/api/spatiotemporal/predict",
            json={
                "model_id": model_id,
                "target_positions": {"x": [120.15], "y": [30.15], "z": [10.2]},
                "target_times": [1712448000],
                "prediction_days": 7,
                "options": {"backend_available": False, "online_preferred": True, "use_cache": False},
            },
        )
        assert offline_predict.status_code == 200, offline_predict.text
        assert offline_predict.json()["data"]["summary"]["mode"] == "offline"

        inc_resp = client.post(
            "/api/spatiotemporal/incremental-update",
            json={
                "model_id": model_id,
                "new_data": {
                    "x": [120.7, 120.8, 120.9],
                    "y": [30.7, 30.8, 30.9],
                    "z": [12.2, 12.4, 12.6],
                    "t": [1712620800, 1712707200, 1712793600],
                    "value": [84.0, 84.4, 84.9],
                },
            },
        )
        assert inc_resp.status_code == 200, inc_resp.text
        assert inc_resp.json()["data"]["model_id"] == model_id

        list_resp = client.get("/api/spatiotemporal/models?page=1&page_size=5")
        assert list_resp.status_code == 200, list_resp.text
        assert list_resp.json()["data"]["total"] >= 1

        detail_resp = client.get(f"/api/spatiotemporal/models/{model_id}")
        assert detail_resp.status_code == 200, detail_resp.text
        assert detail_resp.json()["data"]["model_id"] == model_id

        warmup_resp = client.post(
            "/api/spatiotemporal/cache/warmup",
            json={
                "model_id": model_id,
                "payloads": [
                    {
                        "target_positions": {"x": [120.2], "y": [30.2], "z": [10.5]},
                        "target_times": [1712880000],
                        "prediction_days": 3,
                    }
                ],
            },
        )
        assert warmup_resp.status_code == 200, warmup_resp.text

        metrics_resp = client.get("/api/spatiotemporal/performance/metrics")
        assert metrics_resp.status_code == 200, metrics_resp.text
        metrics = metrics_resp.json()["data"]
        assert "prediction_engine" in metrics
        assert "memory" in metrics

        delete_resp = client.delete(f"/api/spatiotemporal/models/{model_id}")
        assert delete_resp.status_code == 200, delete_resp.text

        missing_resp = client.get(f"/api/spatiotemporal/models/{model_id}")
        assert missing_resp.status_code == 404, missing_resp.text
        assert missing_resp.json()["error"]["code"] == "1001"
