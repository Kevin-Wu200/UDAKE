import numpy as np
import pytest

from app.core.spatiotemporal_kriging.st_kriging_solver import STKrigingSolver
from app.services.spatiotemporal_core import STDataset, SpatiotemporalVariogramModeler


def _dataset(n: int = 14) -> STDataset:
    x = np.linspace(120.0, 121.0, n)
    y = np.linspace(30.0, 31.0, n)
    z = np.linspace(10.0, 16.0, n)
    t = np.linspace(1711929600, 1711929600 + 86400 * (n - 1), n)
    value = 80.0 + np.sin(np.linspace(0.0, 2.0, n))
    return STDataset(x=x, y=y, z=z, t=t, value=value)


def _fitted_params(data: STDataset, model_type: str = "product") -> dict:
    modeler = SpatiotemporalVariogramModeler()
    return modeler.fit(data, model_type)["parameters"]


def test_covariance_matrix_and_low_rank_info() -> None:
    data = _dataset(18)
    solver = STKrigingSolver(block_size=6, temporal_window_size=6, low_rank=6)
    modeler = SpatiotemporalVariogramModeler()
    params = _fitted_params(data)

    points = np.column_stack([data.coords, data.t])
    k, info = solver.covariance_matrix(
        points=points,
        params=params,
        model_type="product",
        covariance_builder=modeler.build_covariance_function,
        use_low_rank=True,
    )

    assert k.shape == (18, 18)
    assert np.all(np.isfinite(k))
    assert info["target_rank"] == 6
    assert "low_rank_used" in info


def test_solve_cholesky_and_parallel() -> None:
    solver = STKrigingSolver()
    matrix = np.array([[4.0, 1.0], [1.0, 3.0]], dtype=np.float64)
    rhs = np.array([1.0, 2.0], dtype=np.float64)

    x = solver.solve_cholesky(matrix, rhs)
    assert np.allclose(matrix @ x, rhs, atol=1e-6)

    xs = solver.solve_parallel_cholesky(matrix, [rhs, rhs * 2])
    assert len(xs) == 2
    assert np.allclose(matrix @ xs[1], rhs * 2, atol=1e-6)


def test_weight_prediction_and_uncertainty_output() -> None:
    data = _dataset(12)
    solver = STKrigingSolver(block_size=8, temporal_window_size=5, low_rank=5)
    modeler = SpatiotemporalVariogramModeler()
    params = _fitted_params(data, "separated")

    result = solver.predict(
        train_data=data,
        targets={
            "x": [120.15, 120.45],
            "y": [30.12, 30.42],
            "z": [10.5, 11.8],
        },
        target_times=[1712016000.0, 1712102400.0],
        params=params,
        model_type="separated",
        covariance_builder=modeler.build_covariance_function,
    )

    assert len(result["predictions"]) == 4
    assert len(result["weights"]) == 4
    assert all(row["variance"] > 0 for row in result["predictions"])
    assert all(len(w) == len(data.x) for w in result["weights"])


def test_predict_invalid_target_input_raises() -> None:
    data = _dataset(8)
    solver = STKrigingSolver()
    modeler = SpatiotemporalVariogramModeler()
    params = _fitted_params(data)

    with pytest.raises(ValueError, match="目标点和目标时间不能为空"):
        solver.predict(
            train_data=data,
            targets={"x": [], "y": [], "z": []},
            target_times=[],
            params=params,
            model_type="product",
            covariance_builder=modeler.build_covariance_function,
        )

    with pytest.raises(ValueError, match="长度必须一致"):
        solver.predict(
            train_data=data,
            targets={"x": [120.1], "y": [30.1, 30.2], "z": [10.1]},
            target_times=[1712016000.0],
            params=params,
            model_type="product",
            covariance_builder=modeler.build_covariance_function,
        )


def test_block_temporal_and_merge_helpers() -> None:
    data = _dataset(20)
    solver = STKrigingSolver(block_size=5, temporal_window_size=6, low_rank=4)

    blocks = solver.spatial_blocks(data.coords, overlap_ratio=0.2)
    assert len(blocks) >= 4
    assert all(len(b) >= 1 for b in blocks)

    windows = solver.temporal_windows(data.t, step=4, overlap=2)
    assert len(windows) >= 3

    merged = solver.merge_window_predictions([
        np.array([1.0, 2.0, 3.0]),
        np.array([1.5, 2.5, 3.5]),
    ])
    assert np.allclose(merged, np.array([1.25, 2.25, 3.25]))
