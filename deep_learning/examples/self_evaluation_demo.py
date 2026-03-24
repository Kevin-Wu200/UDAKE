"""阶段11用户验证与模型自评估系统示例。"""

from __future__ import annotations

from pprint import pprint

from services.backend.app.services.self_evaluation_service import SelfEvaluationService


def build_records() -> list[dict]:
    rows = []
    for i in range(10):
        pred = 15.0 + i * 0.25
        actual = pred + (0.12 if i % 2 else -0.08)
        rows.append(
            {
                "evaluation_id": f"demo_{i}",
                "dataset_id": "demo_dataset",
                "model_id": "st_transformer",
                "module": "realtime_interpolation",
                "x": 120.0 + i * 0.01,
                "y": 30.0 + i * 0.01,
                "predicted_value": pred,
                "actual_value": actual,
                "result": "accept" if i % 3 else "correct",
                "confidence": 0.6 + 0.03 * (i % 4),
                "uncertainty": 0.1 + 0.02 * (i % 3),
                "interval_lower": pred - 0.4,
                "interval_upper": pred + 0.4,
                "response_time_seconds": 0.8 + i * 0.2,
                "verification_time_seconds": 1.2 + i * 0.15,
                "features": [0.1 * i, 0.05 * i],
            }
        )
    return rows


def main() -> None:
    service = SelfEvaluationService()

    realtime = service.evaluate_realtime({"records": build_records(), "window_minutes": 120, "sample_size": 500})
    pprint(realtime["performance"])

    model_selection = service.select_best_model(
        {
            "candidates": [
                {
                    "model_id": "m1",
                    "model_name": "baseline",
                    "performance_score": 0.74,
                    "uncertainty_score": 0.30,
                    "scenario_score": 0.60,
                },
                {
                    "model_id": "m2",
                    "model_name": "new_model",
                    "performance_score": 0.83,
                    "uncertainty_score": 0.20,
                    "scenario_score": 0.68,
                },
            ],
            "auto_switch": True,
            "switch_min_gain": 0.01,
        }
    )
    pprint(model_selection)

    task = service.trigger_optimization({"trigger_type": "manual", "async": False, "data_volume": 120})
    pprint(task)

    report = service.generate_report({"report_type": "all", "format": "json", "window_minutes": 120, "sample_size": 500})
    pprint({"report_id": report["report_id"], "report_type": report["report_type"]})


if __name__ == "__main__":
    main()
