import numpy as np
import pytest

from app.core.spatiotemporal_kriging.st_model_selector import STModelSelector


def test_metric_calculations() -> None:
    selector = STModelSelector()
    y_true = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    y_pred = np.array([1.1, 1.9, 2.8, 4.2], dtype=np.float64)
    std = np.array([0.2, 0.2, 0.3, 0.4], dtype=np.float64)

    assert selector.rmse(y_true, y_pred) > 0
    assert selector.mae(y_true, y_pred) > 0
    assert selector.crps(y_true, y_pred, std) > 0
    assert selector.uncertainty_calibration_score(y_true, y_pred, std) >= 0


def test_evaluate_with_variance_and_weights() -> None:
    selector = STModelSelector()
    y_true = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    y_pred = np.array([10.5, 11.1, 11.8, 13.3], dtype=np.float64)
    variance = np.array([0.1, 0.2, 0.2, 0.3], dtype=np.float64)

    result = selector.evaluate(
        y_true,
        y_pred,
        variance=variance,
        weights={"rmse": 0.4, "mae": 0.2, "crps": 0.3, "calibration": 0.1},
    )

    assert set(result.keys()) == {"rmse", "mae", "crps", "calibration_score", "score"}
    assert result["rmse"] > 0
    assert result["score"] > 0


def test_model_evaluation_selection_and_report() -> None:
    selector = STModelSelector()
    evaluations = {
        "separated": {"score": 0.42, "rmse": 0.20, "mae": 0.15, "crps": 0.05, "calibration_score": 0.02},
        "product": {"score": 0.35, "rmse": 0.18, "mae": 0.12, "crps": 0.04, "calibration_score": 0.01},
        "nonseparable": {"score": 0.30, "rmse": 0.16, "mae": 0.10, "crps": 0.03, "calibration_score": 0.01},
    }

    best = selector.select_best(evaluations)
    assert best == "nonseparable"

    report = selector.generate_report(best, evaluations)
    assert report["best_model"] == "nonseparable"
    assert report["ranked_models"][0]["model"] == "nonseparable"
    assert "generated_at" in report


def test_evaluate_and_select_input_validation() -> None:
    selector = STModelSelector()

    with pytest.raises(ValueError, match="评估数据不能为空"):
        selector.evaluate(np.array([]), np.array([]))

    with pytest.raises(ValueError, match="评估结果不能为空"):
        selector.select_best({})
