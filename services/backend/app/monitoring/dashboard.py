"""Dashboard summary for product-key validation observability."""

from __future__ import annotations

from typing import Any, Dict


class ValidationDashboard:
    def __init__(self, metrics: Any, validation_cache: Any, alerting: Any) -> None:
        self._metrics = metrics
        self._cache = validation_cache
        self._alerting = alerting

    def snapshot(self) -> Dict[str, Any]:
        base = self._metrics.snapshot()
        cache_metrics = self._cache.metrics()
        alerts = self._alerting.evaluate(base, cache_hit_rate=float(cache_metrics.get("hit_rate", 0.0)))
        return {
            "metrics": base,
            "cache": cache_metrics,
            "alerts": alerts,
            "recent_alerts": self._alerting.latest(limit=20),
        }
