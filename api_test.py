"""
后端 API 冒烟集成测试
"""

import pytest


def test_root_endpoint(integration_client):
    resp = integration_client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert "version" in body


def test_health_endpoint(integration_client):
    resp = integration_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_docs_endpoint(integration_client):
    resp = integration_client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


def test_upload_endpoint_rejects_invalid_json(integration_client):
    files = {"file": ("invalid.geojson", b"not-json", "application/geo+json")}
    resp = integration_client.post("/api/upload-data", files=files)
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "method,path,payload,ok_statuses",
    [
        ("GET", "/api/system/status", None, {200}),
        ("GET", "/api/cache/statistics", None, {200}),
        ("GET", "/api/multi-objective/config", None, {200}),
        ("POST", "/api/sampling-impact/evaluate-candidates", {}, {200, 422}),
        ("POST", "/api/sampling-impact/preview-effect", {}, {200, 422}),
        ("POST", "/api/sampling-impact/recommend-optimal", {}, {200, 422}),
        ("POST", "/api/sampling-impact/batch-simulate", {}, {200, 422}),
    ],
)
def test_api_contract_smoke(integration_client, method, path, payload, ok_statuses):
    if method == "GET":
        resp = integration_client.get(path)
    elif method == "POST":
        resp = integration_client.post(path, json=payload)
    else:
        raise AssertionError(f"unsupported method: {method}")

    assert resp.status_code in ok_statuses, resp.text
