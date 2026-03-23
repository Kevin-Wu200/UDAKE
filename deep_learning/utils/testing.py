"""测试框架基类与报告工具。"""

from __future__ import annotations

import json
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class BaseTestCase(unittest.TestCase):
    """统一测试基类。"""

    def assertFloatAlmostEqual(self, left: float, right: float, delta: float = 1e-6) -> None:
        self.assertTrue(abs(left - right) <= delta, f"{left} !~= {right}")


@dataclass
class PerformanceResult:
    name: str
    duration_ms: float
    success: bool


class PerformanceTestRunner:
    def run(self, name: str, fn: Callable[[], Any], max_duration_ms: float) -> PerformanceResult:
        start = time.perf_counter()
        fn()
        duration_ms = (time.perf_counter() - start) * 1000
        return PerformanceResult(name=name, duration_ms=duration_ms, success=duration_ms <= max_duration_ms)


class TestReportGenerator:
    def write_json(self, path: str, payload: dict[str, Any]) -> str:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(file_path)
