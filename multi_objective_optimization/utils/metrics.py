"""
性能指标计算工具
Performance metrics utility functions
"""

import numpy as np
from typing import List, Dict, Any
from ..core.population import Population, Individual


def calculate_hypervolume(
    population: Population,
    reference_point: np.ndarray = None
) -> float:
    """
    计算超体积指标

    Args:
        population: 种群
        reference_point: 参考点（如果为None，自动计算）

    Returns:
        float: 超体积值
    """
    pareto_front = population.get_pareto_front()

    if len(pareto_front) == 0:
        return 0.0

    # 获取所有目标函数值
    objectives_array = np.array([ind.objectives for ind in pareto_front])

    # 如果没有提供参考点，自动计算
    if reference_point is None:
        reference_point = np.max(objectives_array, axis=0) * 1.1

    # 计算超体积（简化版本）
    # 注意：这是简化实现，实际应该使用更精确的算法
    hv = 0.0

    for i, ind in enumerate(pareto_front):
        # 计算该个体相对于参考点的体积
        volume = 1.0
        for j in range(len(ind.objectives)):
            volume *= max(0, reference_point[j] - ind.objectives[j])

        # 简化的贡献计算（实际应该考虑支配关系）
        hv += volume / len(pareto_front)

    return hv


def calculate_spacing(population: Population) -> float:
    """
    计算间距指标（衡量帕累托前沿的分布均匀性）

    Args:
        population: 种群

    Returns:
        float: 间距值
    """
    pareto_front = population.get_pareto_front()

    if len(pareto_front) < 2:
        return 0.0

    # 计算所有个体之间的距离
    distances = []

    for i, ind1 in enumerate(pareto_front):
        for j, ind2 in enumerate(pareto_front):
            if i != j:
                dist = np.linalg.norm(ind1.objectives - ind2.objectives)
                distances.append(dist)

    distances = np.array(distances)

    # 计算平均距离
    mean_distance = np.mean(distances)

    # 计算间距指标
    spacing = np.sqrt(np.mean((distances - mean_distance) ** 2))

    return spacing


def calculate_spread(population: Population) -> float:
    """
    计算分布度指标（衡量帕累托前沿的覆盖范围）

    Args:
        population: 种群

    Returns:
        float: 分布度值
    """
    pareto_front = population.get_pareto_front()

    if len(pareto_front) < 2:
        return 0.0

    # 获取所有目标函数值
    objectives_array = np.array([ind.objectives for ind in pareto_front])

    # 计算每个目标的最大最小距离
    n_objectives = objectives_array.shape[1]
    extreme_distances = []

    for obj_idx in range(n_objectives):
        obj_values = objectives_array[:, obj_idx]
        extreme_distances.append(np.max(obj_values) - np.min(obj_values))

    # 计算分布度
    spread = np.sum(extreme_distances)

    return spread


def calculate_igd(
    population: Population,
    true_pareto_front: np.ndarray
) -> float:
    """
    计算IGD指标（反代际距离）

    Args:
        population: 种群
        true_pareto_front: 真实的帕累托前沿

    Returns:
        float: IGD值
    """
    pareto_front = population.get_pareto_front()

    if len(pareto_front) == 0 or len(true_pareto_front) == 0:
        return float('inf')

    # 获取当前帕累托前沿的目标函数值
    current_objectives = np.array([ind.objectives for ind in pareto_front])

    # 计算真实前沿中每个点到当前前沿的最小距离
    distances = []

    for true_point in true_pareto_front:
        min_dist = float('inf')
        for current_point in current_objectives:
            dist = np.linalg.norm(true_point - current_point)
            min_dist = min(min_dist, dist)
        distances.append(min_dist)

    # 计算平均距离
    igd = np.mean(distances)

    return igd


def calculate_convergence_rate(
    convergence_history: List[Dict[str, Any]],
    objective_index: int = 0
) -> float:
    """
    计算收敛率

    Args:
        convergence_history: 收敛历史
        objective_index: 目标函数索引

    Returns:
        float: 收敛率
    """
    if len(convergence_history) < 2:
        return 0.0

    # 获取第一代和最后一代的目标函数值
    first_gen = convergence_history[0]['best_objectives'][objective_index]
    last_gen = convergence_history[-1]['best_objectives'][objective_index]

    # 计算改进率
    if first_gen == 0:
        return 0.0

    improvement = (first_gen - last_gen) / first_gen
    return improvement


def calculate_diversity(population: Population) -> float:
    """
    计算多样性指标

    Args:
        population: 种群

    Returns:
        float: 多样性值
    """
    pareto_front = population.get_pareto_front()

    if len(pareto_front) < 2:
        return 0.0

    # 计算所有个体之间的平均距离
    total_distance = 0.0
    count = 0

    for i, ind1 in enumerate(pareto_front):
        for j, ind2 in enumerate(pareto_front):
            if i < j:
                dist = np.linalg.norm(ind1.objectives - ind2.objectives)
                total_distance += dist
                count += 1

    if count == 0:
        return 0.0

    avg_distance = total_distance / count

    return avg_distance


def calculate_pareto_front_size(population: Population) -> int:
    """
    计算帕累托前沿的大小

    Args:
        population: 种群

    Returns:
        int: 帕累托前沿的大小
    """
    return len(population.get_pareto_front())


def calculate_feasible_ratio(population: Population) -> float:
    """
    计算可行解比例

    Args:
        population: 种群

    Returns:
        float: 可行解比例
    """
    if len(population) == 0:
        return 0.0

    n_feasible = sum(1 for ind in population if ind.is_feasible)
    return n_feasible / len(population)


def calculate_constraint_violation(population: Population) -> float:
    """
    计算平均约束违反程度

    Args:
        population: 种群

    Returns:
        float: 平均约束违反程度
    """
    if len(population) == 0:
        return 0.0

    total_violation = sum(ind.constraints_violation for ind in population)
    return total_violation / len(population)


def calculate_performance_metrics(population: Population) -> Dict[str, Any]:
    """
    计算所有性能指标

    Args:
        population: 种群

    Returns:
        Dict: 所有性能指标
    """
    metrics = {
        'hypervolume': calculate_hypervolume(population),
        'spacing': calculate_spacing(population),
        'spread': calculate_spread(population),
        'diversity': calculate_diversity(population),
        'pareto_front_size': calculate_pareto_front_size(population),
        'feasible_ratio': calculate_feasible_ratio(population),
        'constraint_violation': calculate_constraint_violation(population),
    }

    return metrics


def calculate_generation_statistics(population: Population) -> Dict[str, Any]:
    """
    计算代统计信息

    Args:
        population: 种群

    Returns:
        Dict: 代统计信息
    """
    pareto_front = population.get_pareto_front()

    if len(pareto_front) == 0:
        return {}

    objectives_array = np.array([ind.objectives for ind in pareto_front])

    stats = {
        'generation': population.generation,
        'population_size': population.size,
        'pareto_front_size': len(pareto_front),
        'objective_statistics': {
            'means': np.mean(objectives_array, axis=0).tolist(),
            'stds': np.std(objectives_array, axis=0).tolist(),
            'mins': np.min(objectives_array, axis=0).tolist(),
            'maxs': np.max(objectives_array, axis=0).tolist(),
        }
    }

    return stats