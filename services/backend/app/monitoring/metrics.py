"""Metrics collector for key validation pipeline."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict


class ValidationMetrics:
    def __init__(self, *, max_samples: int = 5000) -> None:
        self._lock = threading.Lock()
        self._count = 0
        self._success = 0
        self._failed = 0
        self._errors = 0
        self._durations: Deque[int] = deque(maxlen=max(100, int(max_samples)))
        self._last_updated = int(time.time())

    def record(self, *, valid: bool, processing_time_ms: int, is_error: bool = False) -> None:
        with self._lock:
            self._count += 1
            if valid:
                self._success += 1
            else:
                self._failed += 1
            if is_error:
                self._errors += 1
            self._durations.append(max(0, int(processing_time_ms)))
            self._last_updated = int(time.time())

    def snapshot(self) -> Dict[str, float]:
        with self._lock:
            values = sorted(self._durations)
            count = len(values)
            avg = float(sum(values) / count) if count else 0.0

            def percentile(ratio: float) -> float:
                if not values:
                    return 0.0
                idx = int((count - 1) * ratio)
                return float(values[max(0, min(count - 1, idx))])

            total = max(1, self._count)
            return {
                "validation_count": float(self._count),
                "validation_success_rate": float(self._success / total),
                "validation_error_rate": float(self._errors / total),
                "avg_response_time_ms": avg,
                "p95_response_time_ms": percentile(0.95),
                "p99_response_time_ms": percentile(0.99),
                "last_updated": float(self._last_updated),
            }
