"""
种群和个体类
Population and Individual classes
"""

import numpy as np
from typing import List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class Individual:
    """
    个体类，表示一个候选解
    Individual class representing a candidate solution
    """
    genes: np.ndarray = None  # 基因（采样点索引）
    objectives: np.ndarray = None  # 目标函数值
    rank: int = 0  # 非支配等级
    crowding_distance: float = 0.0  # 拥挤度
    constraints_violation: float = 0.0  # 约束违反程度
    is_feasible: bool = True  # 是否可行
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据

    def __post_init__(self):
        if self.genes is None:
            self.genes = np.array([], dtype=int)
        if self.objectives is None:
            self.objectives = np.array([], dtype=float)

    def dominates(self, other: 'Individual') -> bool:
        """
        判断当前个体是否支配另一个个体
        Check if this individual dominates another individual

        Args:
            other: 另一个个体

        Returns:
            bool: 如果支配返回True，否则返回False
        """
        if not self.is_feasible and other.is_feasible:
            return False
        if self.is_feasible and not other.is_feasible:
            return True
        if not self.is_feasible and not other.is_feasible:
            return self.constraints_violation < other.constraints_violation

        all_better_or_equal = np.all(self.objectives <= other.objectives)
        at_least_one_better = np.any(self.objectives < other.objectives)

        return all_better_or_equal and at_least_one_better

    def copy(self) -> 'Individual':
        """
        创建个体的深拷贝
        Create a deep copy of the individual

        Returns:
            Individual: 个体副本
        """
        new_individual = Individual()
        new_individual.genes = self.genes.copy()
        new_individual.objectives = self.objectives.copy()
        new_individual.rank = self.rank
        new_individual.crowding_distance = self.crowding_distance
        new_individual.constraints_violation = self.constraints_violation
        new_individual.is_feasible = self.is_feasible
        new_individual.metadata = self.metadata.copy()
        return new_individual


class Population:
    """
    种群类，管理所有个体
    Population class managing all individuals
    """

    def __init__(self, size: int = 0):
        """
        初始化种群

        Args:
            size: 种群规模
        """
        self.individuals: List[Individual] = []
        self.size: int = size
        self.fronts: List[List[int]] = []  # 前沿面
        self.generation: int = 0  # 当前代数

    def add_individual(self, individual: Individual):
        """
        添加个体到种群

        Args:
            individual: 要添加的个体
        """
        self.individuals.append(individual)
        self.size = len(self.individuals)

    def get_individual(self, index: int) -> Individual:
        """
        获取指定索引的个体

        Args:
            index: 个体索引

        Returns:
            Individual: 个体对象
        """
        return self.individuals[index]

    def get_pareto_front(self) -> List[Individual]:
        """
        获取帕累托前沿（第一前沿面）

        Returns:
            List[Individual]: 帕累托前沿个体列表
        """
        if len(self.fronts) == 0:
            return []
        return [self.individuals[i] for i in self.fronts[0]]

    def get_all_fronts(self) -> List[List[Individual]]:
        """
        获取所有前沿面

        Returns:
            List[List[Individual]]: 所有前沿面
        """
        return [[self.individuals[i] for i in front] for front in self.fronts]

    def shuffle(self):
        """随机打乱种群中个体的顺序"""
        np.random.shuffle(self.individuals)

    def sort_by_objective(self, objective_index: int = 0):
        """
        根据指定目标函数值排序

        Args:
            objective_index: 目标函数索引
        """
        self.individuals.sort(key=lambda ind: ind.objectives[objective_index])

    def filter_feasible(self) -> 'Population':
        """
        过滤出可行个体

        Returns:
            Population: 只包含可行个体的新种群
        """
        feasible_pop = Population()
        feasible_pop.individuals = [ind for ind in self.individuals if ind.is_feasible]
        feasible_pop.size = len(feasible_pop.individuals)
        return feasible_pop

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取种群统计信息

        Returns:
            Dict: 统计信息字典
        """
        if len(self.individuals) == 0:
            return {}

        objectives_array = np.array([ind.objectives for ind in self.individuals])
        n_feasible = sum(1 for ind in self.individuals if ind.is_feasible)

        stats = {
            'size': self.size,
            'n_feasible': n_feasible,
            'n_infeasible': self.size - n_feasible,
            'n_fronts': len(self.fronts),
            'pareto_size': len(self.fronts[0]) if self.fronts else 0,
            'generation': self.generation,
            'objective_means': np.mean(objectives_array, axis=0).tolist(),
            'objective_stds': np.std(objectives_array, axis=0).tolist(),
            'objective_mins': np.min(objectives_array, axis=0).tolist(),
            'objective_maxs': np.max(objectives_array, axis=0).tolist(),
        }

        return stats

    def __len__(self) -> int:
        """返回种群大小"""
        return len(self.individuals)

    def __getitem__(self, index: int) -> Individual:
        """支持索引访问"""
        return self.individuals[index]

    def __iter__(self):
        """支持迭代"""
        return iter(self.individuals)