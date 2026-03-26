import json
import sys
import uuid
from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient

# 兼容直接在仓库根目录执行 pytest 的场景
SERVICES_ROOT = Path(__file__).resolve().parent / "services"
if str(SERVICES_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICES_ROOT))

from backend.app.main import app
from backend.app.tasks.任务管理器 import TaskManager
from realtime_interpolation.api import fastapi_routes as realtime_routes
from multi_objective_optimization.api import fastapi_routes as mo_routes


def _build_geojson(point_count: int = 12) -> Dict[str, Any]:
    features = []
    for i in range(point_count):
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(i), float(i + 1)],
                },
                "properties": {"value": float(10 + i)},
            }
        )
    return {"type": "FeatureCollection", "features": features}


@pytest.fixture
def integration_client():
    # 每个测试前清理全局状态，避免跨测试污染
    TaskManager().reset()
    realtime_routes.realtime_service.subscriptions.clear()
    if realtime_routes.realtime_service.cache_manager:
        realtime_routes.realtime_service.cache_manager.clear()
    mo_routes.tasks_db.clear()

    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_geojson() -> Dict[str, Any]:
    return _build_geojson()


@pytest.fixture
def uploaded_data_id(integration_client, sample_geojson) -> str:
    payload = json.dumps(sample_geojson).encode("utf-8")
    files = {"file": ("test_data.geojson", payload, "application/geo+json")}
    resp = integration_client.post("/api/upload-data", files=files)
    assert resp.status_code == 200, resp.text
    return resp.json()["data_id"]


@pytest.fixture
def realtime_subscription_payload() -> Dict[str, Any]:
    sub_id = f"sub-{uuid.uuid4().hex[:8]}"
    return {
        "subscription_id": sub_id,
        "data_type": "generic",
        "spatial_extent": {
            "min_x": 0.0,
            "min_y": 0.0,
            "max_x": 10.0,
            "max_y": 10.0,
        },
        "update_frequency": 1,
        "interpolation_params": {"grid_resolution": 10},
        "notification_config": {},
    }
