"""后端服务目录下的跨项目包路径桥接。"""
from __future__ import annotations

from pathlib import Path

_REAL_PACKAGE_DIR = Path(__file__).resolve().parents[3] / "multi_objective_optimization"
__path__ = [str(_REAL_PACKAGE_DIR)]

# 重新导出真实包中的符号，确保 from multi_objective_optimization import X 可用
# 由于 __path__ 已指向真实包目录，使用包内相对导入即可
from .core.nsga2 import NSGA2Optimizer  # noqa: E402
from .core.optimizer import BaseOptimizer  # noqa: E402
from .core.population import Individual, Population  # noqa: E402
from .objectives.accessibility import AccessibilityObjective  # noqa: E402
from .objectives.base import BaseObjective  # noqa: E402
from .objectives.cost import CostObjective  # noqa: E402
from .objectives.variance import VarianceObjective  # noqa: E402
from .constraints.base import BaseConstraint  # noqa: E402
from .constraints.boundary import BoundaryConstraint  # noqa: E402
from .constraints.budget import BudgetConstraint  # noqa: E402
from .constraints.distance import DistanceConstraint  # noqa: E402
from .constraints.time_window import TimeWindowConstraint  # noqa: E402

__all__ = [
    'BaseOptimizer', 'NSGA2Optimizer', 'Population', 'Individual',
    'BaseObjective', 'VarianceObjective', 'CostObjective', 'AccessibilityObjective',
    'BaseConstraint', 'BoundaryConstraint', 'DistanceConstraint', 'BudgetConstraint',
    'TimeWindowConstraint',
]
