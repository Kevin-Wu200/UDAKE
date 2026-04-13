from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backend.app.api_response import unified_api_response_middleware
from services.backend.app.api_versioning import api_versioning_middleware
from services.backend.app.dl_services.api import router


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def _version_mw(request, call_next):
        return await api_versioning_middleware(request, call_next)

    @app.middleware("http")
    async def _response_mw(request, call_next):
        return await unified_api_response_middleware(request, call_next)

    app.include_router(router, prefix="/api")
    return app

def _spatial_payload() -> tuple[list[list[float]], list[list[float]]]:
    samples = [
        [0.10, 0.10, 1.20],
        [0.20, 0.15, 1.35],
        [0.35, 0.40, 1.10],
        [0.55, 0.60, 0.75],
        [0.75, 0.20, 1.60],
        [0.80, 0.75, 0.50],
    ]
    queries = [[0.12, 0.11], [0.55, 0.52]]
    return samples, queries


def test_v2_response_wrapper_for_success() -> None:
    client = TestClient(_build_app())
    resp = client.get("/api/v2/dl/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["code"] == "OK"
    assert payload["meta"]["api_version"] == "2.0"
    assert payload["data"]["status"] == "healthy"
    assert "request_id" in payload["meta"]


def test_invalid_model_type_returns_validation_error() -> None:
    client = TestClient(_build_app())
    resp = client.post(
        "/api/v2/dl/models/explain",
        json={"model_type": "unknown", "payload": {}},
    )
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["success"] is False
    assert payload["code"] == "VALIDATION_ERROR"
    assert "支持类型" in str(payload["error"])


def test_generic_param_conversion_and_dispatch() -> None:
    client = TestClient(_build_app())
    samples, queries = _spatial_payload()
    resp = client.post(
        "/api/v2/dl/models/explain",
        json={
            "model_type": "interpolation",
            "model_name": "gnn",
            "method": "lime",
            "top_k": "3",
            "max_explain_nodes": "4",
            "num_samples": "120",
            "sample_count": str(len(samples)),
            "payload": {
                "samples": samples,
                "queries": queries,
                "interpolation_radius": 1.2,
                "weight_function": "gaussian",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["model_type"] == "gnn"
    assert body["data"]["summary"]["method"] == "lime"


def test_model_router_cache_hit() -> None:
    client = TestClient(_build_app())
    samples, queries = _spatial_payload()

    before = client.get("/api/v2/dl/models/router/stats").json()["data"]
    first = client.post(
        "/api/v2/dl/models/explain",
        json={
            "model_type": "interpolation",
            "model_name": "gnn",
            "method": "lime",
            "top_k": 3,
            "payload": {
                "samples": samples,
                "queries": queries,
                "weight_function": "gaussian",
            },
        },
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v2/dl/models/explain",
        json={
            "model_type": "interpolation",
            "model_name": "gnn",
            "method": "lime",
            "top_k": 3,
            "payload": {
                "samples": samples,
                "queries": queries,
                "weight_function": "gaussian",
            },
        },
    )
    assert second.status_code == 200
    after = client.get("/api/v2/dl/models/router/stats").json()["data"]
    assert after["hits"] >= before["hits"] + 1
