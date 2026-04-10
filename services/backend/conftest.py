import warnings
import sys
import json
import importlib
from pathlib import Path
from typing import Any, Dict

import pytest

# 确保无论从哪个工作目录执行 pytest，都能导入仓库根目录下的模块（如 ai_extension）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 抑制 macOS LibreSSL 与 urllib3 v2 的兼容性警告
warnings.filterwarnings("ignore", message=".*urllib3.*LibreSSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="urllib3")

# 抑制 starlette 对 multipart 导入兼容层的待弃用提示
warnings.filterwarnings(
    "ignore",
    message=".*import python_multipart.*",
    category=PendingDeprecationWarning,
    module="starlette\\.formparsers"
)


def _import_any(*module_names: str):
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
    pytest.skip(f"Required module missing. Tried: {', '.join(module_names)}")


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
    testclient = pytest.importorskip("fastapi.testclient")
    backend_main = _import_any("app.main", "backend.app.main")
    task_manager_mod = _import_any("app.tasks.任务管理器", "backend.app.tasks.任务管理器")
    realtime_routes = _import_any(
        "realtime_interpolation.api.fastapi_routes",
        "backend.realtime_interpolation.api.fastapi_routes",
    )
    mo_routes = _import_any(
        "multi_objective_optimization.api.fastapi_routes",
        "backend.multi_objective_optimization.api.fastapi_routes",
    )

    app = backend_main.app
    task_manager_mod.TaskManager().reset()
    realtime_routes.realtime_service.subscriptions.clear()
    if realtime_routes.realtime_service.cache_manager:
        realtime_routes.realtime_service.cache_manager.clear()
    mo_routes.tasks_db.clear()

    with testclient.TestClient(app) as client:
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
