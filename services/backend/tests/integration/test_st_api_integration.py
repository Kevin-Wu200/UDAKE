from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

services_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(services_root))

from backend.app.main import app


def _train_payload(model_type: str = "separated") -> dict:
    return {
        "data": {
            "x": [120.1, 120.2, 120.3, 120.4, 120.5],
            "y": [30.1, 30.2, 30.3, 30.4, 30.5],
            "z": [10.0, 10.4, 10.8, 11.2, 11.6],
            "t": [1711929600, 1712016000, 1712102400, 1712188800, 1712275200],
            "value": [80.0, 81.2, 82.0, 82.7, 83.3],
        },
        "model_type": model_type,
        "options": {},
    }


def test_st_api_data_validation_and_error_response() -> None:
    with TestClient(app) as client:
        invalid_resp = client.post(
            "/api/spatiotemporal/train",
            json={
                "data": {
                    "x": [120.1, 120.2, 120.3],
                    "y": [30.1, 30.2],
                    "z": [10.0, 10.1, 10.2],
                    "t": [1, 2, 3],
                    "value": [80, 81, 82],
                },
                "model_type": "product",
            },
        )
        assert invalid_resp.status_code == 422

        missing_model_resp = client.post(
            "/api/spatiotemporal/predict",
            json={
                "model_id": "st_model_missing",
                "target_positions": {"x": [120.2], "y": [30.2], "z": [10.3]},
                "target_times": [1712361600],
                "prediction_days": 3,
                "options": {"include_uncertainty": True},
            },
            headers={"X-Request-ID": "req_st_api_integration"},
        )
        assert missing_model_resp.status_code == 404
        body = missing_model_resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "1001"
        assert body["error"]["request_id"] == "req_st_api_integration"
        assert "timestamp" in body["error"]


def test_st_api_call_and_response_format() -> None:
    with TestClient(app) as client:
        train_resp = client.post("/api/spatiotemporal/train", json=_train_payload("product"))
        assert train_resp.status_code == 200, train_resp.text
        train_data = train_resp.json()["data"]
        model_id = train_data["model_id"]

        predict_resp = client.post(
            "/api/spatiotemporal/predict",
            json={
                "model_id": model_id,
                "target_positions": {"x": [120.25, 120.35], "y": [30.25, 30.35], "z": [10.5, 11.0]},
                "target_times": [1712361600, 1712448000],
                "prediction_days": 7,
                "options": {"use_cache": True, "backend_available": True},
            },
        )
        assert predict_resp.status_code == 200, predict_resp.text
        payload = predict_resp.json()
        assert payload["success"] is True
        assert payload["data"]["model_id"] == model_id
        assert payload["data"]["summary"]["total_predictions"] == 4

        auto_resp = client.post(
            "/api/spatiotemporal/auto-select",
            json={
                "historical_data": _train_payload()["data"],
                "new_samples": _train_payload()["data"],
                "prediction_results": {
                    "separated": [{"predicted": 80.0}],
                    "product": [{"predicted": 80.2}],
                    "nonseparated": [{"predicted": 79.9}],
                },
                "options": {},
            },
        )
        assert auto_resp.status_code == 200, auto_resp.text
        auto_data = auto_resp.json()["data"]
        assert set(auto_data["evaluation"].keys()) == {"separated", "product", "nonseparable"}
