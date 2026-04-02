"""API 版本管理测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api_versioning import api_versioning_middleware, resolve_api_version


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def _versioning(request: Request, call_next):
        return await api_versioning_middleware(request, call_next)

    @app.get("/api/ping")
    async def ping():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return TestClient(app)


def test_resolve_version_from_header() -> None:
    result = resolve_api_version(path="/api/ping", header_version="2")
    assert result.version == "2.0"
    assert result.rewritten_path is None


def test_rewrite_v1_path_and_deprecation_headers(client: TestClient) -> None:
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.headers["X-API-Version"] == "1.0"
    assert response.headers["X-API-Deprecated"] == "true"
    assert response.headers["X-API-Sunset"] == "2026-12-31"


def test_rewrite_v2_path(client: TestClient) -> None:
    response = client.get("/api/v2/ping")
    assert response.status_code == 200
    assert response.headers["X-API-Version"] == "2.0"
    assert "X-API-Deprecated" not in response.headers


def test_reject_unsupported_header_version(client: TestClient) -> None:
    response = client.get("/api/ping", headers={"X-API-Version": "3.0"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_api_version"
    assert "不受支持" in body["detail"]


def test_reject_conflicting_versions(client: TestClient) -> None:
    response = client.get("/api/v1/ping", headers={"X-API-Version": "2.0"})
    assert response.status_code == 400
    assert "不一致" in response.json()["detail"]


def test_non_api_route_is_not_versioned(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-API-Version" not in response.headers
