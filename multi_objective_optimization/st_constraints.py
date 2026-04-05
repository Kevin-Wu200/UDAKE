"""时空采样约束。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .st_objectives import STSamplingPoint


@dataclass
class STConstraintConfig:
    max_samples: int = 20
    min_distance: float = 0.01
    max_time_span: float = 7 * 86400.0


class STConstraints:
    """时空约束检查器。"""

    def __init__(self, config: STConstraintConfig | None = None) -> None:
        self.config = config or STConstraintConfig()

    def sample_count_violation(self, points: Sequence[STSamplingPoint]) -> float:
        return float(max(0, len(points) - self.config.max_samples))

    def min_distance_violation(self, points: Sequence[STSamplingPoint]) -> float:
        if len(points) < 2:
            return 0.0
        violation = 0.0
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                d = float(np.hypot(points[i].x - points[j].x, points[i].y - points[j].y))
                if d < self.config.min_distance:
                    violation += self.config.min_distance - d
        return violation

    def time_span_violation(self, points: Sequence[STSamplingPoint]) -> float:
        if len(points) <= 1:
            return 0.0
        times = np.array([p.t for p in points], dtype=float)
        return float(max(0.0, float(np.max(times) - np.min(times)) - self.config.max_time_span))

    def total_violation(self, points: Sequence[STSamplingPoint]) -> float:
        return float(
            self.sample_count_violation(points)
            + self.min_distance_violation(points)
            + self.time_span_violation(points)
        )
