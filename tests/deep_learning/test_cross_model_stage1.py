from __future__ import annotations

import time
from typing import Any

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backend.app.dl_services.api import explain_task_service, router
from services.backend.app.dl_services.service import DeepLearningService


def _make_anomaly_data(n: int = 48, seed: int = 301) -> tuple[list[list[float]], list[float]]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.3) + np.cos(coords[:, 1] * 3.2) + rng.normal(0.0, 0.05, size=n)
    values[::13] += 1.0
    return coords.tolist(), values.astype(float).tolist()


def _make_interpolation_data(seed: int = 302) -> tuple[list[list[float]], list[list[float]]]:
    rng = np.random.default_rng(seed)
    samples_xy = rng.uniform(0.0, 1.0, size=(36, 2))
    sample_values = np.sin(samples_xy[:, 0] * 4.0) + np.cos(samples_xy[:, 1] * 2.8)
    samples = np.column_stack([samples_xy, sample_values]).astype(float).tolist()
    queries = rng.uniform(0.1, 0.9, size=(8, 2)).astype(float).tolist()
    return samples, queries


def _make_uncertainty_features(seed: int = 303) -> list[list[float]]:
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, size=(40, 5))
    x[:, 0] += np.linspace(-1.0, 1.0, 40)
    return x.astype(float).tolist()


def _make_fusion_payload() -> tuple[list[dict[str, Any]], list[float]]:
    models = [
        {
            "model_id": "m1",
            "model_name": "gnn_kriging",
            "predictions": [1.0, 1.2, 1.1, 1.3, 1.25, 1.35],
            "variances": [0.05, 0.05, 0.06, 0.05, 0.05, 0.06],
        },
        {
            "model_id": "m2",
            "model_name": "attention_kriging",
            "predictions": [0.95, 1.25, 1.05, 1.28, 1.2, 1.33],
            "variances": [0.07, 0.06, 0.07, 0.07, 0.08, 0.07],
        },
        {
            "model_id": "m3",
            "model_name": "residual_kriging",
            "predictions": [1.05, 1.18, 1.12, 1.27, 1.22, 1.31],
            "variances": [0.06, 0.06, 0.06, 0.06, 0.06, 0.06],
        },
    ]
    true_values = [1.0, 1.2, 1.1, 1.3, 1.24, 1.34]
    return models, true_values


def _make_uncertainty_map(size: int = 10) -> list[list[float]]:
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    arr = np.clip(0.4 + 0.25 * np.sin(xx * 3.2) + 0.18 * np.cos(yy * 2.4), 0.01, 1.0)
    return arr.astype(float).tolist()


def _signature(payload: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    summary = payload.get("summary", {})
    features = tuple(
        (item.get("feature_name"), item.get("feature_index"))
        for item in (summary.get("top_features") or [])[:3]
    )
    return str(summary.get("method", "")), features


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


def _wait_task_completed(
    client: TestClient,
    get_url: str,
    *,
    headers: dict[str, str],
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        resp = client.get(get_url, headers=headers)
        assert resp.status_code == 200
        payload = resp.json()
        status = payload.get("status")
        if status in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"task not finished in {timeout_seconds}s: {get_url}")


def test_cross_model_lime_and_shap_accuracy_stability_repeatability() -> None:
    service = DeepLearningService()

    anomaly_coords, anomaly_values = _make_anomaly_data()
    interp_samples, interp_queries = _make_interpolation_data()
    uncertainty_features = _make_uncertainty_features()
    fusion_models, fusion_true = _make_fusion_payload()
    rl_map = _make_uncertainty_map()
    rl_points = [[0.2, 0.2], [0.7, 0.65]]

    run_cases: list[tuple[str, dict[str, Any]]] = [
        (
            "anomaly",
            dict(
                fn=service.explain_anomaly,
                kwargs=dict(
                    model_name="vae",
                    coords=anomaly_coords,
                    values=anomaly_values,
                    top_k=4,
                    max_explain_nodes=4,
                    include_prediction=True,
                    num_samples=100,
                    nsamples=80,
                ),
            ),
        ),
        (
            "interpolation",
            dict(
                fn=service.explain_interpolation,
                kwargs=dict(
                    model_type="gnn",
                    samples=interp_samples,
                    queries=interp_queries,
                    top_k=4,
                    max_explain_nodes=4,
                    include_prediction=True,
                    num_samples=100,
                    nsamples=80,
                ),
            ),
        ),
        (
            "uncertainty",
            dict(
                fn=service.explain_uncertainty,
                kwargs=dict(
                    model_name="bnn",
                    features=uncertainty_features,
                    top_k=4,
                    max_explain_nodes=4,
                    include_prediction=True,
                    num_samples=100,
                    nsamples=80,
                ),
            ),
        ),
        (
            "fusion",
            dict(
                fn=service.explain_fusion,
                kwargs=dict(
                    models=fusion_models,
                    true_values=fusion_true,
                    strategy="dynamic",
                    weight_method="adaptive",
                    top_k=4,
                    max_explain_nodes=4,
                    include_prediction=True,
                    num_samples=100,
                    nsamples=80,
                ),
            ),
        ),
        (
            "rl",
            dict(
                fn=service.explain_sampling_rl,
                kwargs=dict(
                    model_name="ppo",
                    uncertainty_map=rl_map,
                    existing_points=rl_points,
                    top_k=4,
                    max_explain_nodes=4,
                    n_recommendations=6,
                    include_prediction=True,
                    num_samples=100,
                    nsamples=80,
                ),
            ),
        ),
    ]

    for scope, cfg in run_cases:
        for method in ("lime", "shap"):
            kwargs = dict(cfg["kwargs"])
            kwargs["method"] = method
            out1 = cfg["fn"](**kwargs)
            out2 = cfg["fn"](**kwargs)

            assert out1["summary"]["method"] == method, f"{scope}-{method} method mismatch"
            assert "summary" in out1 and isinstance(out1["summary"].get("top_features"), list)
            assert "prediction" in out1, f"{scope}-{method} should include prediction for frontend display"
            assert _signature(out1) == _signature(out2), f"{scope}-{method} should be repeatable and stable"


@pytest.mark.parametrize(
    ("scope", "post_url", "get_url_tpl", "payload"),
    [
        (
            "anomaly",
            "/api/dl/anomaly/explain",
            "/api/dl/anomaly/explain/{task_id}",
            lambda: {
                "model_name": "vae",
                "coords": _make_anomaly_data()[0],
                "values": _make_anomaly_data()[1],
                "method": "hybrid",
                "top_k": 3,
                "max_explain_nodes": 4,
                "async_mode": True,
            },
        ),
        (
            "interpolation",
            "/api/dl/interpolation/explain",
            "/api/dl/interpolation/explain/{task_id}",
            lambda: {
                "model_type": "gnn",
                "samples": _make_interpolation_data()[0],
                "queries": _make_interpolation_data()[1],
                "method": "hybrid",
                "top_k": 3,
                "max_explain_nodes": 4,
                "async_mode": True,
            },
        ),
        (
            "uncertainty",
            "/api/dl/uncertainty/explain",
            "/api/dl/uncertainty/explain/{task_id}",
            lambda: {
                "model_name": "bnn",
                "features": _make_uncertainty_features(),
                "method": "hybrid",
                "top_k": 3,
                "max_explain_nodes": 4,
                "async_mode": True,
            },
        ),
        (
            "fusion",
            "/api/dl/fusion/explain",
            "/api/dl/fusion/explain/{task_id}",
            lambda: {
                "models": _make_fusion_payload()[0],
                "true_values": _make_fusion_payload()[1],
                "strategy": "dynamic",
                "weight_method": "adaptive",
                "method": "hybrid",
                "top_k": 3,
                "max_explain_nodes": 4,
                "async_mode": True,
            },
        ),
        (
            "rl",
            "/api/dl/rl/explain",
            "/api/dl/rl/explain/{task_id}",
            lambda: {
                "model_name": "ppo",
                "uncertainty_map": _make_uncertainty_map(),
                "existing_points": [[0.18, 0.21], [0.64, 0.58]],
                "method": "hybrid",
                "top_k": 3,
                "max_explain_nodes": 4,
                "n_recommendations": 5,
                "async_mode": True,
            },
        ),
    ],
)
def test_cross_model_async_task_create_status_and_result(
    scope: str,
    post_url: str,
    get_url_tpl: str,
    payload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = scope
    explain_task_service.reset_for_testing()
    app = _build_app()
    client = TestClient(app)
    headers = {"x-user-id": "cross-model-user"}

    def _fake_execute(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": {"method": str(data.get("method", "hybrid")), "top_features": []},
            "prediction": {"ok": True},
            "scope": str(data.get("scope", "")),
        }

    monkeypatch.setattr(explain_task_service, "_execute_explanation", _fake_execute)

    create_resp = client.post(post_url, json=payload(), headers=headers)
    assert create_resp.status_code == 200
    create_json = create_resp.json()
    assert create_json["status"] == "queued"
    assert "task_id" in create_json
    assert "queue_size" in create_json

    task_id = create_json["task_id"]
    status_json = _wait_task_completed(client, get_url_tpl.format(task_id=task_id), headers=headers)
    assert status_json["status"] == "completed"
    assert status_json.get("result", {}).get("summary", {}).get("method") == "hybrid"
    assert "prediction" in status_json.get("result", {})


@pytest.mark.parametrize(
    ("post_url", "cancel_url_tpl", "get_url_tpl", "payload"),
    [
        (
            "/api/dl/anomaly/explain",
            "/api/dl/anomaly/explain/{task_id}/cancel",
            "/api/dl/anomaly/explain/{task_id}",
            lambda: {
                "model_name": "vae",
                "coords": _make_anomaly_data()[0],
                "values": _make_anomaly_data()[1],
                "method": "hybrid",
                "async_mode": True,
            },
        ),
        (
            "/api/dl/interpolation/explain",
            "/api/dl/interpolation/explain/{task_id}/cancel",
            "/api/dl/interpolation/explain/{task_id}",
            lambda: {
                "model_type": "gnn",
                "samples": _make_interpolation_data()[0],
                "queries": _make_interpolation_data()[1],
                "method": "hybrid",
                "async_mode": True,
            },
        ),
        (
            "/api/dl/uncertainty/explain",
            "/api/dl/uncertainty/explain/{task_id}/cancel",
            "/api/dl/uncertainty/explain/{task_id}",
            lambda: {
                "model_name": "bnn",
                "features": _make_uncertainty_features(),
                "method": "hybrid",
                "async_mode": True,
            },
        ),
        (
            "/api/dl/fusion/explain",
            "/api/dl/fusion/explain/{task_id}/cancel",
            "/api/dl/fusion/explain/{task_id}",
            lambda: {
                "models": _make_fusion_payload()[0],
                "true_values": _make_fusion_payload()[1],
                "method": "hybrid",
                "async_mode": True,
            },
        ),
        (
            "/api/dl/rl/explain",
            "/api/dl/rl/explain/{task_id}/cancel",
            "/api/dl/rl/explain/{task_id}",
            lambda: {
                "model_name": "ppo",
                "uncertainty_map": _make_uncertainty_map(),
                "existing_points": [[0.2, 0.2], [0.7, 0.6]],
                "method": "hybrid",
                "async_mode": True,
            },
        ),
    ],
)
def test_cross_model_async_task_cancel(
    post_url: str,
    cancel_url_tpl: str,
    get_url_tpl: str,
    payload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explain_task_service.reset_for_testing()
    app = _build_app()
    client = TestClient(app)
    headers = {"x-user-id": "cancel-user"}

    def _slow_execute(data: dict[str, Any]) -> dict[str, Any]:
        _ = data
        time.sleep(0.3)
        return {"summary": {"method": "hybrid"}, "prediction": {"ok": True}}

    monkeypatch.setattr(explain_task_service, "_execute_explanation", _slow_execute)

    create = client.post(post_url, json=payload(), headers=headers)
    assert create.status_code == 200
    task_id = create.json()["task_id"]

    cancel = client.post(cancel_url_tpl.format(task_id=task_id), headers=headers)
    assert cancel.status_code == 200
    assert cancel.json()["cancelled"] is True

    status_json = _wait_task_completed(client, get_url_tpl.format(task_id=task_id), headers=headers)
    assert status_json["status"] in {"cancelled", "completed"}


def test_cross_model_async_task_error_handling_and_api_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explain_task_service.reset_for_testing()
    app = _build_app()
    client = TestClient(app)
    headers = {"x-user-id": "error-user"}

    def _raise_execute(data: dict[str, Any]) -> dict[str, Any]:
        _ = data
        raise RuntimeError("simulated async failure")

    monkeypatch.setattr(explain_task_service, "_execute_explanation", _raise_execute)

    create = client.post(
        "/api/dl/anomaly/explain",
        json={
            "model_name": "vae",
            "coords": _make_anomaly_data()[0],
            "values": _make_anomaly_data()[1],
            "method": "hybrid",
            "async_mode": True,
        },
        headers=headers,
    )
    assert create.status_code == 200
    task_id = create.json()["task_id"]
    status_json = _wait_task_completed(client, f"/api/dl/anomaly/explain/{task_id}", headers=headers)
    assert status_json["status"] == "failed"
    assert "simulated async failure" in str(status_json.get("error"))

    invalid = client.post(
        "/api/dl/rl/explain",
        json={
            "model_name": "ppo",
            "uncertainty_map": _make_uncertainty_map(),
            "top_k": 0,
        },
    )
    assert invalid.status_code == 422
    assert "greater than or equal to 1" in invalid.text
