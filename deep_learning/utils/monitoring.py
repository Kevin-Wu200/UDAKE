"""监控与告警工具。"""

from __future__ import annotations

from dataclasses import dataclass
import statistics
import time


@dataclass
class AlertRule:
    metric: str
    threshold: float
    operator: str = ">="


class MetricMonitor:
    def __init__(self) -> None:
        self.metrics: dict[str, list[tuple[float, float]]] = {}

    def log(self, name: str, value: float, timestamp: float | None = None) -> None:
        if timestamp is None:
            timestamp = time.time()
        self.metrics.setdefault(name, []).append((timestamp, float(value)))

    def summary(self, name: str) -> dict[str, float]:
        values = [v for _, v in self.metrics.get(name, [])]
        if not values:
            return {"count": 0.0, "min": 0.0, "max": 0.0, "mean": 0.0}
        return {
            "count": float(len(values)),
            "min": float(min(values)),
            "max": float(max(values)),
            "mean": float(statistics.fmean(values)),
        }


class SystemResourceMonitor:
    def collect(self) -> dict[str, float]:
        try:
            import psutil  # type: ignore
        except Exception:
            return {"cpu_percent": 0.0, "memory_percent": 0.0}
        return {
            "cpu_percent": float(psutil.cpu_percent(interval=None)),
            "memory_percent": float(psutil.virtual_memory().percent),
        }


class AlertManager:
    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self.rules = rules or []

    def evaluate(self, latest_metrics: dict[str, float]) -> list[str]:
        alerts: list[str] = []
        for rule in self.rules:
            value = latest_metrics.get(rule.metric)
            if value is None:
                continue
            triggered = value >= rule.threshold if rule.operator == ">=" else value <= rule.threshold
            if triggered:
                alerts.append(f"{rule.metric}={value:.4f} 触发阈值 {rule.operator} {rule.threshold:.4f}")
        return alerts
