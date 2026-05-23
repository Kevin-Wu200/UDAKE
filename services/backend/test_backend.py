"""
后端关键链路集成测试（基于 TestClient 生命周期 fixture）
"""

import json

import pytest


def test_health_check(integration_client):
    resp = integration_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_upload_data(integration_client, sample_geojson):
    files = {
        "file": (
            "test_data.geojson",
            json.dumps(sample_geojson).encode("utf-8"),
            "application/geo+json",
        )
    }
    resp = integration_client.post("/api/upload-data", files=files)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["point_count"] == len(sample_geojson["features"])
    assert "data_id" in body and len(body["data_id"]) >= 8


@pytest.fixture
def recommended_params(integration_client, uploaded_data_id):
    resp = integration_client.post(
        "/api/recommend-parameters",
        json={"data_id": uploaded_data_id, "enable_auto_model": True},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_recommend_parameters(recommended_params):
    assert recommended_params["recommended_variogram_model"] in {
        "spherical",
        "exponential",
        "gaussian",
        "linear",
    }
    assert recommended_params["recommended_method"] in {"ordinary", "universal", "block"}
    assert recommended_params["recommended_grid_resolution"] > 0


@pytest.fixture
def started_task_id(integration_client, uploaded_data_id, recommended_params):
    payload = {
        "data_id": uploaded_data_id,
        "variogram_model": recommended_params["recommended_variogram_model"],
        "method": recommended_params["recommended_method"],
        "grid_resolution": recommended_params["recommended_grid_resolution"],
        "nlags": recommended_params["recommended_nlags"],
        "enable_cross_validation": False,
        "n_folds": 3,
    }
    resp = integration_client.post("/api/start-kriging", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["task_id"]


def test_start_kriging(started_task_id):
    assert isinstance(started_task_id, str)
    assert len(started_task_id) >= 8


def test_task_status(integration_client, started_task_id):
    resp = integration_client.get(f"/api/task-status/{started_task_id}")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["task_id"] == started_task_id
    assert body["status"] in {"pending", "running", "completed", "failed"}
    assert "progress" in body


def test_get_results(integration_client, started_task_id):
    prediction_resp = integration_client.get(f"/api/result/prediction/{started_task_id}")
    variance_resp = integration_client.get(f"/api/result/variance/{started_task_id}")

    assert prediction_resp.status_code in {200, 404}
    assert variance_resp.status_code in {200, 404}

    if prediction_resp.status_code == 200:
        assert "geotiff_url" in prediction_resp.json()
    if variance_resp.status_code == 200:
        assert "geotiff_url" in variance_resp.json()
