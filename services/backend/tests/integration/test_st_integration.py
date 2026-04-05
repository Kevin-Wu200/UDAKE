import asyncio

import numpy as np
import pytest

from app.services.spatiotemporal_kriging_service import SpatiotemporalKrigingService


def _series(n: int = 8) -> dict:
    x = np.linspace(120.0, 120.7, n).tolist()
    y = np.linspace(30.0, 30.7, n).tolist()
    z = np.linspace(10.0, 12.8, n).tolist()
    t = np.linspace(1711929600, 1711929600 + 86400 * (n - 1), n).tolist()
    value = (80.0 + 1.8 * np.sin(np.linspace(0.0, 1.5, n))).tolist()
    return {"x": x, "y": y, "z": z, "t": t, "value": value}


def test_st_service_module_integration_workflow() -> None:
    service = SpatiotemporalKrigingService()

    trained = service.train_model(_series(10), model_type="nonseparable")
    model_id = trained["model_id"]
    assert trained["model_type"] == "nonseparable"

    prediction = asyncio.run(
        service.predict(
            model_id=model_id,
            target_positions={"x": [120.2, 120.4], "y": [30.2, 30.4], "z": [10.5, 11.5]},
            target_times=[1712016000.0],
            prediction_days=7,
            options={"backend_available": True, "use_cache": False},
        )
    )
    assert prediction["summary"]["mode"] == "online"
    assert prediction["summary"]["total_predictions"] == 2

    new_samples = _series(4)
    auto_selected = service.auto_select_model(
        historical_data=_series(10),
        new_samples=new_samples,
        prediction_results=None,
        options={"n_samples": 2},
    )
    assert auto_selected["best_model"] in {"separated", "product", "nonseparable"}
    assert len(auto_selected["sampling_plan"]["selected_points"]) == 2

    update = service.incremental_update_model(
        model_id=model_id,
        new_data={
            "x": [120.8, 120.9, 121.0],
            "y": [30.8, 30.9, 31.0],
            "z": [13.0, 13.2, 13.4],
            "t": [1712793600, 1712880000, 1712966400],
            "value": [81.6, 81.9, 82.1],
        },
    )
    assert update["model_id"] == model_id
    assert update["data_stats"]["total_samples"] == 13


def test_st_service_data_flow_and_error_handling() -> None:
    service = SpatiotemporalKrigingService()

    with pytest.raises(ValueError, match="至少需要 3 个样本点"):
        service.train_model(
            {
                "x": [120.0, 120.1],
                "y": [30.0, 30.1],
                "z": [10.0, 10.1],
                "t": [1711929600, 1712016000],
                "value": [80.0, 80.2],
            },
            model_type="product",
        )

    trained = service.train_model(_series(6), model_type="separated")
    model_id = trained["model_id"]

    with pytest.raises(KeyError, match="模型不存在"):
        asyncio.run(
            service.predict(
                model_id="st_model_not_exists",
                target_positions={"x": [120.1], "y": [30.1], "z": [10.1]},
                target_times=[1712016000.0],
                prediction_days=3,
            )
        )

    with pytest.raises(ValueError, match="prediction_days"):
        asyncio.run(
            service.predict(
                model_id=model_id,
                target_positions={"x": [120.1], "y": [30.1], "z": [10.1]},
                target_times=[1712016000.0],
                prediction_days=16,
            )
        )
