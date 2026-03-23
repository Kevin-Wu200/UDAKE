from __future__ import annotations

from deep_learning.utils.testing import PerformanceTestRunner, TestReportGenerator


def test_performance_runner_and_report(tmp_path) -> None:
    runner = PerformanceTestRunner()
    result = runner.run("noop", lambda: sum(range(1000)), max_duration_ms=100)
    assert result.success is True

    report_path = TestReportGenerator().write_json(
        str(tmp_path / "reports" / "deep_learning_report.json"),
        {
            "suite": "deep_learning",
            "tests": 1,
            "performance": {"noop_ms": result.duration_ms},
        },
    )
    assert report_path.endswith("deep_learning_report.json")
