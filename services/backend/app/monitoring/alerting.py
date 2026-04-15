"""Simple threshold-based alerting for validation metrics."""

from __future__ import annotations

from typing import Any, Dict, List


class ValidationAlerting:
    def __init__(self, cache_backend: Any) -> None:
        self._cache = cache_backend
        self._alerts_key = "monitoring:validation:alerts"

    def evaluate(self, metrics: Dict[str, float], *, cache_hit_rate: float) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        if float(metrics.get("p95_response_time_ms", 0.0)) > 500.0:
            alerts.append({"level": "warning", "type": "response_time", "message": "P95响应时间超过500ms"})
        if float(metrics.get("validation_error_rate", 0.0)) > 0.05:
            alerts.append({"level": "warning", "type": "error_rate", "message": "验证错误率超过5%"})
        if float(cache_hit_rate) < 0.5:
            alerts.append({"level": "warning", "type": "cache_hit_rate", "message": "缓存命中率低于50%"})
        if alerts:
            history = self._cache.get(self._alerts_key)
            rows = list(history) if isinstance(history, list) else []
            rows.extend(alerts)
            self._cache.set(self._alerts_key, rows[-500:], ttl=7 * 24 * 60 * 60)
        return alerts

    def latest(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._cache.get(self._alerts_key)
        data = list(rows) if isinstance(rows, list) else []
        return data[-max(1, int(limit)) :]
