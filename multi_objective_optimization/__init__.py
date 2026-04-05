"""
多目标优化采样系统
Multi-Objective Optimization Sampling System
"""

__version__ = "1.0.0"
__author__ = "iFlow CLI"

from .core.optimizer import BaseOptimizer
from .core.nsga2 import NSGA2Optimizer
from .core.population import Population, Individual
from .objectives.base import BaseObjective
from .objectives.variance import VarianceObjective
from .objectives.cost import CostObjective
from .objectives.accessibility import AccessibilityObjective
from .constraints.base import BaseConstraint
from .constraints.boundary import BoundaryConstraint
from .constraints.distance import DistanceConstraint
from .constraints.budget import BudgetConstraint
from .st_objectives import STSamplingPoint, STObjectiveFunctions
from .st_constraints import STConstraintConfig, STConstraints
from .st_sampling_optimizer import STSamplingOptimizer, STOptimizationResult

__all__ = [
    'BaseOptimizer',
    'NSGA2Optimizer',
    'Population',
    'Individual',
    'BaseObjective',
    'VarianceObjective',
    'CostObjective',
    'AccessibilityObjective',
    'BaseConstraint',
    'BoundaryConstraint',
    'DistanceConstraint',
    'BudgetConstraint',
    'STSamplingPoint',
    'STObjectiveFunctions',
    'STConstraintConfig',
    'STConstraints',
    'STSamplingOptimizer',
    'STOptimizationResult',
]
