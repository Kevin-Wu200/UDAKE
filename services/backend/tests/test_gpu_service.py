"""GPU服务单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.gpu_service import GPUService


@pytest.fixture
def service() -> GPUService:
    return GPUService(force_cpu=True)


def test_health_and_config(service: GPUService) -> None:
    health = service.get_health()
    assert health["status"] == "healthy"
    assert health["backend"] == "cpu"

    config = service.update_config(enable_gpu=False, auto_switch=False, min_size_for_gpu=10)
    assert config["enable_gpu"] is False
    assert config["auto_switch"] is False
    assert config["min_size_for_gpu"] == 10


def test_matrix_multiply_and_inverse(service: GPUService) -> None:
    multiply = service.matrix_multiply([[1, 2], [3, 4]], [[2], [1]], prefer_gpu=True)
    result = np.asarray(multiply["result"]["result"])
    np.testing.assert_allclose(result, np.array([[4], [10]]))

    inverse = service.matrix_inverse([[4, 7], [2, 6]], prefer_gpu=True)
    inv = np.asarray(inverse["result"]["result"])
    identity = inv @ np.array([[4, 7], [2, 6]], dtype=float)
    np.testing.assert_allclose(identity, np.eye(2), rtol=1e-6, atol=1e-6)


def test_linear_and_vector_ops(service: GPUService) -> None:
    solved = service.solve_linear([[3, 1], [1, 2]], [9, 8], prefer_gpu=True)
    x = np.asarray(solved["result"]["result"])
    np.testing.assert_allclose(x.reshape(-1), np.array([2.0, 3.0]))

    dot = service.vector_dot([1, 2, 3], [4, 5, 6], prefer_gpu=True)
    assert dot["result"]["result"] == pytest.approx(32.0)

    norm = service.vector_norm([3, 4], prefer_gpu=True)
    assert norm["result"]["result"] == pytest.approx(5.0)

    sorted_vec = service.vector_sort([3, 1, 2], prefer_gpu=True)
    assert sorted_vec["result"]["result"] == [1.0, 2.0, 3.0]


def test_kriging_workflow(service: GPUService) -> None:
    sample_points = [[0, 0], [1, 0], [0, 1], [1, 1]]
    sample_values = [1.0, 2.0, 2.0, 3.0]

    variogram = service.kriging_semivariogram(sample_points, sample_values, bins=6, prefer_gpu=True)
    assert len(variogram["result"]["lags"]) == 6
    assert len(variogram["result"]["semivariance"]) == 6

    pred = service.kriging_predict(
        sample_points=sample_points,
        sample_values=sample_values,
        target_points=[[0.5, 0.5], [0.2, 0.7]],
        sill=1.0,
        range_=1.0,
        nugget=0.05,
        prefer_gpu=True,
    )
    assert len(pred["result"]["prediction"]) == 2
    assert len(pred["result"]["variance"]) == 2


def test_task_tracking(service: GPUService) -> None:
    response = service.matrix_multiply([[1]], [[2]], prefer_gpu=True)
    task_id = response["task_id"]

    task = service.get_task(task_id)
    assert task is not None
    assert task["status"] == "completed"

    tasks = service.list_tasks(limit=10)
    assert any(item["task_id"] == task_id for item in tasks)
