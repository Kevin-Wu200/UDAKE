"""
优化器基类
Base Optimizer class
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np
from .population import Population, Individual


class BaseOptimizer(ABC):
    """
    多目标优化器基类
    Base class for multi-objective optimizers
    """

    def __init__(
        self,
        objectives: List,
        constraints: List = None,
        n_candidates: int = 1000,
        n_samples: int = 20,
        random_seed: Optional[int] = None
    ):
        """
        初始化优化器

        Args:
            objectives: 目标函数列表
            constraints: 约束条件列表
            n_candidates: 候选点数量
            n_samples: 采样点数量
            random_seed: 随机种子
        """
        self.objectives = objectives
        self.constraints = constraints if constraints else []
        self.n_candidates = n_candidates
        self.n_samples = n_samples

        if random_seed is not None:
            np.random.seed(random_seed)

        self.convergence_history: List[Dict[str, float]] = []

    @abstractmethod
    def optimize(
        self,
        population_size: int = 100,
        n_generations: int = 100,
        **kwargs
    ) -> Population:
        """
        执行优化

        Args:
            population_size: 种群规模
            n_generations: 进化代数
            **kwargs: 其他参数

        Returns:
            Population: 优化后的种群
        """
        pass

    def evaluate_individual(self, individual: Individual) -> Individual:
        """
        评估个体

        Args:
            individual: 要评估的个体

        Returns:
            Individual: 评估后的个体
        """
        # 评估目标函数
        objective_values = []
        for obj in self.objectives:
            value = obj.evaluate(individual)
            objective_values.append(value)
        individual.objectives = np.array(objective_values)

        # 评估约束条件
        constraint_violation = 0.0
        is_feasible = True

        for constraint in self.constraints:
            violation = constraint.evaluate(individual)
            constraint_violation += violation
            if violation > 0:
                is_feasible = False

        individual.constraints_violation = constraint_violation
        individual.is_feasible = is_feasible

        return individual

    def evaluate_population(self, population: Population) -> Population:
        """
        评估种群中所有个体

        Args:
            population: 要评估的种群

        Returns:
            Population: 评估后的种群
        """
        for i in range(len(population)):
            population.individuals[i] = self.evaluate_individual(population.individuals[i])
        return population

    def initialize_population(self, population_size: int) -> Population:
        """
        初始化种群

        Args:
            population_size: 种群规模

        Returns:
            Population: 初始化的种群
        """
        population = Population()

        for _ in range(population_size):
            individual = self._create_random_individual()
            individual = self.evaluate_individual(individual)
            population.add_individual(individual)

        return population

    def _create_random_individual(self) -> Individual:
        """
        创建随机个体

        Returns:
            Individual: 随机个体
        """
        # 随机选择n_samples个不重复的候选点
        genes = np.random.choice(self.n_candidates, self.n_samples, replace=False)
        individual = Individual()
        individual.genes = genes
        return individual

    def record_convergence(self, generation: int, population: Population):
        """
        记录收敛历史

        Args:
            generation: 当前代数
            population: 当前种群
        """
        pareto_front = population.get_pareto_front()

        if len(pareto_front) > 0:
            objectives_array = np.array([ind.objectives for ind in pareto_front])
            history_entry = {
                'generation': generation,
                'best_objectives': np.min(objectives_array, axis=0).tolist(),
                'avg_objectives': np.mean(objectives_array, axis=0).tolist(),
                'pareto_size': len(pareto_front),
            }
            self.convergence_history.append(history_entry)

    def get_convergence_history(self) -> List[Dict[str, float]]:
        """
        获取收敛历史

        Returns:
            List[Dict]: 收敛历史记录
        """
        return self.convergence_history

    def get_best_solution(self, population: Population, weights: np.ndarray = None) -> Individual:
        """
        获取最优解（基于加权求和）

        Args:
            population: 种群
            weights: 权重向量

        Returns:
            Individual: 最优解
        """
        pareto_front = population.get_pareto_front()

        if len(pareto_front) == 0:
            return None

        if weights is None:
            # 默认均等权重
            weights = np.ones(len(self.objectives)) / len(self.objectives)

        # 归一化目标函数值
        objectives_array = np.array([ind.objectives for ind in pareto_front])
        min_obj = np.min(objectives_array, axis=0)
        max_obj = np.max(objectives_array, axis=0)
        normalized_obj = (objectives_array - min_obj) / (max_obj - min_obj + 1e-10)

        # 计算加权得分
        scores = np.dot(normalized_obj, weights)

        # 返回得分最小的个体
        best_idx = np.argmin(scores)
        return pareto_front[best_idx]

    def validate_input(self) -> bool:
        """
        验证输入参数

        Returns:
            bool: 验证通过返回True
        """
        if len(self.objectives) == 0:
            raise ValueError("至少需要一个目标函数")

        if self.n_candidates <= 0:
            raise ValueError("候选点数量必须大于0")

        if self.n_samples <= 0:
            raise ValueError("采样点数量必须大于0")

        if self.n_samples > self.n_candidates:
            raise ValueError("采样点数量不能超过候选点数量")

        return True