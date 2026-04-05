from __future__ import annotations

from datetime import datetime, timedelta

from realtime_interpolation.core.incremental_st_kriging import IncrementalSTKriging
from realtime_interpolation.models import DataPoint


def _point(idx: int, x: float, y: float, value: float, ts: datetime) -> DataPoint:
    return DataPoint(id=f"p{idx}", x=x, y=y, value=value, timestamp=ts)


def test_incremental_st_kriging_fit_and_update() -> None:
    base = datetime(2026, 4, 1, 0, 0, 0)
    model = IncrementalSTKriging(temporal_scale_seconds=3600, temporal_weight=0.6)

    init_points = [
        _point(1, 0.0, 0.0, 1.0, base),
        _point(2, 1.0, 0.0, 2.0, base + timedelta(hours=1)),
        _point(3, 0.0, 1.0, 2.2, base + timedelta(hours=2)),
    ]
    model.add_initial_points(init_points)

    assert model.covariance_matrix is not None
    assert model.covariance_matrix.shape == (3, 3)

    result = model.incremental_update_st([
        _point(4, 1.0, 1.0, 2.8, base + timedelta(hours=3)),
        _point(5, 1.2, 0.8, 3.1, base + timedelta(hours=4)),
    ])
    assert result["success"] is True
    assert result["updated_points"] == 2
    assert result["total_points"] == 5
    assert model.covariance_matrix_inv is not None
