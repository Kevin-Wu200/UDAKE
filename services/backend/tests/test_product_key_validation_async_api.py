"""Tests for async product-key validation queue endpoints."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.product_keys_api import router as product_keys_router
from app.auth import get_auth_service, reset_auth_service


@pytest.fixture()
def async_product_key_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "product-key-validate-async-secret")
    reset_auth_service()
    app = FastAPI()
    app.include_router(product_keys_router, prefix="/api")
    with TestClient(app) as client:
        yield client
    reset_auth_service()


def test_validate_product_key_async_submit_and_poll(async_product_key_client: TestClient):
    service = get_auth_service()
    record = service.product_keys.generate_key("validate-api-async-seed")

    submit = async_product_key_client.post(
        "/api/product-keys/validate/async",
        json={"product_key": record.product_key},
        headers={"x-forwarded-for": "10.0.0.20", "x-user-id": "u-100"},
    )
    assert submit.status_code == 200
    task_id = submit.json()["data"]["task_id"]

    terminal = None
    for _ in range(30):
        resp = async_product_key_client.get(f"/api/product-keys/validate/async/{task_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        if data["status"] in {"completed", "failed"}:
            terminal = data
            break
        time.sleep(0.05)

    assert terminal is not None
    assert terminal["status"] == "completed"
    assert terminal["result"]["response"]["data"]["valid"] is True


def test_validate_product_key_async_metrics(async_product_key_client: TestClient):
    metrics = async_product_key_client.get("/api/product-keys/validate/async-metrics")
    assert metrics.status_code == 200
    data = metrics.json()["data"]
    assert "queue_size" in data
    assert "tracked_tasks" in data
