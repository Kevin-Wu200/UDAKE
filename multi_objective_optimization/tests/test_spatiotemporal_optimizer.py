from __future__ import annotations

from multi_objective_optimization.st_objectives import STSamplingPoint
from multi_objective_optimization.st_sampling_optimizer import STSamplingOptimizer


def test_st_sampling_optimizer_runs() -> None:
    candidates = [
        STSamplingPoint(x=120.0 + i * 0.01, y=30.0 + i * 0.01, t=1711929600 + i * 3600, uncertainty=1.0 + (i % 4))
        for i in range(16)
    ]

    optimizer = STSamplingOptimizer(random_seed=7)
    result = optimizer.optimize(candidates=candidates, n_samples=6, population_size=24, n_generations=12)

    assert len(result.selected_indices) == 6
    assert len(result.selected_points) == 6
    assert result.objectives["uncertainty"] >= 0.0
    assert result.pareto_size >= 1
