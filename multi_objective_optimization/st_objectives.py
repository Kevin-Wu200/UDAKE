"""时空采样目标函数。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import numpy as np


@dataclass
class STSamplingPoint:
    x: float
    y: float
    t: float
    uncertainty: float


class STObjectiveFunctions:
    """时空目标函数集合：精度与成本。"""

    @staticmethod
    def uncertainty_objective(points: Sequence[STSamplingPoint]) -> float:
        if not points:
            return 0.0
        return float(np.mean([max(0.0, p.uncertainty) for p in points]))

    @staticmethod
    def travel_cost_objective(points: Sequence[STSamplingPoint], speed: float = 12.0) -> float:
        if len(points) <= 1:
            return 0.0
        ordered = sorted(points, key=lambda p: p.t)
        distance = 0.0
        for i in range(1, len(ordered)):
            dx = ordered[i].x - ordered[i - 1].x
            dy = ordered[i].y - ordered[i - 1].y
            distance += float(np.hypot(dx, dy))
        travel_time = distance / max(float(speed), 1e-6)
        return float(distance + 0.1 * travel_time)

    @staticmethod
    def evaluate(points: Sequence[STSamplingPoint]) -> Tuple[float, float]:
        return (
            STObjectiveFunctions.uncertainty_objective(points),
            STObjectiveFunctions.travel_cost_objective(points),
        )

    @staticmethod
    def from_raw(rows: Iterable[dict]) -> List[STSamplingPoint]:
        result: List[STSamplingPoint] = []
        for row in rows:
            result.append(
                STSamplingPoint(
                    x=float(row.get("x", 0.0)),
                    y=float(row.get("y", 0.0)),
                    t=float(row.get("t", 0.0)),
                    uncertainty=float(row.get("uncertainty", row.get("variance", 0.0))),
                )
            )
        return result
