"""时空采样优化器（NSGA-II扩展）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .constraints.base import BaseConstraint
from .core.nsga2 import NSGA2Optimizer
from .core.population import Individual
from .objectives.base import BaseObjective
from .st_constraints import STConstraintConfig, STConstraints
from .st_objectives import STObjectiveFunctions, STSamplingPoint


class _STUncertaintyObjective(BaseObjective):
    def __init__(self, candidates: Sequence[STSamplingPoint]):
        super().__init__(name="st_uncertainty", weight=1.0, direction="minimize")
        self.candidates = list(candidates)

    def evaluate(self, individual: Individual) -> float:
        points = [self.candidates[int(idx)] for idx in individual.genes]
        return STObjectiveFunctions.uncertainty_objective(points)


class _STCostObjective(BaseObjective):
    def __init__(self, candidates: Sequence[STSamplingPoint]):
        super().__init__(name="st_cost", weight=1.0, direction="minimize")
        self.candidates = list(candidates)

    def evaluate(self, individual: Individual) -> float:
        points = [self.candidates[int(idx)] for idx in individual.genes]
        return STObjectiveFunctions.travel_cost_objective(points)


class _STConstraint(BaseConstraint):
    def __init__(self, candidates: Sequence[STSamplingPoint], constraints: STConstraints):
        super().__init__(name="st_constraints")
        self.candidates = list(candidates)
        self.constraints = constraints

    def evaluate(self, individual: Individual) -> float:
        points = [self.candidates[int(idx)] for idx in individual.genes]
        return self.constraints.total_violation(points)


@dataclass
class STOptimizationResult:
    selected_indices: List[int]
    selected_points: List[Dict[str, float]]
    objectives: Dict[str, float]
    pareto_size: int


class STSamplingOptimizer:
    """扩展 NSGA-II 到时空采样点优化。"""

    def __init__(self, random_seed: int = 42) -> None:
        self.random_seed = random_seed

    def optimize(
        self,
        candidates: Sequence[STSamplingPoint],
        n_samples: int = 12,
        population_size: int = 40,
        n_generations: int = 30,
        constraint_config: STConstraintConfig | None = None,
    ) -> STOptimizationResult:
        if len(candidates) < max(2, n_samples):
            raise ValueError("候选点数量不足，无法执行时空采样优化")

        constraints = STConstraints(config=constraint_config)
        objectives = [_STUncertaintyObjective(candidates), _STCostObjective(candidates)]
        hard_constraints = [_STConstraint(candidates, constraints)]

        optimizer = NSGA2Optimizer(
            objectives=objectives,
            constraints=hard_constraints,
            n_candidates=len(candidates),
            n_samples=int(n_samples),
            random_seed=self.random_seed,
        )
        population = optimizer.optimize(
            population_size=int(population_size),
            n_generations=int(n_generations),
            crossover_prob=0.9,
            mutation_prob=0.12,
            verbose=False,
        )

        best = optimizer.get_best_solution(population)
        if best is None:
            raise RuntimeError("NSGA-II 未产生可用解")

        selected_indices = [int(v) for v in best.genes.tolist()]
        selected = [candidates[i] for i in selected_indices]
        uncertainty, cost = STObjectiveFunctions.evaluate(selected)

        return STOptimizationResult(
            selected_indices=selected_indices,
            selected_points=[
                {"x": float(p.x), "y": float(p.y), "t": float(p.t), "uncertainty": float(p.uncertainty)}
                for p in selected
            ],
            objectives={"uncertainty": float(uncertainty), "cost": float(cost)},
            pareto_size=len(population.get_pareto_front()),
        )
