"""
前后端通讯集成测试（前端依赖的后端契约）
"""

import pytest


def test_frontend_required_pages(integration_client):
    root_resp = integration_client.get("/")
    docs_resp = integration_client.get("/docs")

    assert root_resp.status_code == 200
    assert docs_resp.status_code == 200
    assert "text/html" in docs_resp.headers.get("content-type", "")


def test_basic_api_contract(integration_client):
    health_resp = integration_client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "healthy"


def test_data_upload_and_parameter_recommendation(integration_client, uploaded_data_id):
    resp = integration_client.post(
        "/api/recommend-parameters",
        json={"data_id": uploaded_data_id, "enable_auto_model": True},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["point_count"] > 0
    assert "recommended_variogram_model" in body
    assert "recommended_method" in body


def test_realtime_interpolation_workflow(integration_client, realtime_subscription_payload):
    # 1) 创建订阅
    create_resp = integration_client.post("/api/subscriptions", json=realtime_subscription_payload)
    assert create_resp.status_code == 200, create_resp.text
    sub_id = realtime_subscription_payload["subscription_id"]

    # 2) 添加数据点
    point_payload = {"x": 1.0, "y": 1.0, "value": 12.3}
    add_resp = integration_client.post(f"/api/subscriptions/{sub_id}/data-points", json=point_payload)
    assert add_resp.status_code == 200, add_resp.text

    # 3) 查询预测
    pred_resp = integration_client.get(
        f"/api/subscriptions/{sub_id}/prediction",
        params={"x": 1.0, "y": 1.0},
    )
    assert pred_resp.status_code == 200, pred_resp.text
    pred_body = pred_resp.json()
    assert "prediction" in pred_body
    assert "variance" in pred_body

    # 4) 删除订阅
    del_resp = integration_client.delete(f"/api/subscriptions/{sub_id}")
    assert del_resp.status_code == 200, del_resp.text


def test_multi_objective_workflow(integration_client):
    optimize_payload = {
        "variance_grid": {
            "data": [[0.2, 0.3], [0.4, 0.5]],
            "bounds": {"minX": 0, "minY": 0, "maxX": 1, "maxY": 1},
        },
        "existing_points": [{"x": 0.1, "y": 0.1}],
        "n_samples": 3,
        "weights": {"variance": 0.5, "cost": 0.3, "accessibility": 0.2},
        "constraints": {"boundary": {"minX": 0, "minY": 0, "maxX": 1, "maxY": 1}},
        "algorithm": "NSGA-II",
        "algorithm_params": {"n_candidates": 50},
        "is_async": True,
    }

    create_resp = integration_client.post("/api/multi-objective/optimize", json=optimize_payload)
    assert create_resp.status_code == 200, create_resp.text
    task_id = create_resp.json()["data"]["task_id"]

    info_resp = integration_client.get(f"/api/multi-objective/tasks/{task_id}")
    assert info_resp.status_code == 200
    assert info_resp.json()["data"]["task_id"] == task_id

    status_resp = integration_client.get(f"/api/multi-objective/tasks/{task_id}/status")
    assert status_resp.status_code == 200

    cancel_resp = integration_client.delete(f"/api/multi-objective/tasks/{task_id}")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["status"] == "cancelled"


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/sampling-impact/evaluate-candidates", {}),
        ("/api/sampling-impact/preview-effect", {}),
        ("/api/sampling-impact/recommend-optimal", {}),
        ("/api/sampling-impact/batch-simulate", {}),
    ],
)
def test_sampling_impact_endpoints_validation(integration_client, path, payload):
    resp = integration_client.post(path, json=payload)
    # 这里重点是接口可访问且无 500
    assert resp.status_code in {200, 422}, resp.text


def test_advanced_status_endpoints(integration_client):
    system_status_resp = integration_client.get("/api/system/status")
    cache_stats_resp = integration_client.get("/api/cache/statistics")
    task_list_resp = integration_client.get("/api/multi-objective/tasks")

    assert system_status_resp.status_code == 200
    assert cache_stats_resp.status_code == 200
    assert task_list_resp.status_code == 200
