"""
NSGA-II算法实现
NSGA-II Algorithm Implementation
"""

import numpy as np
from typing import List, Tuple
import time
from .optimizer import BaseOptimizer
from .population import Population, Individual


class NSGA2Optimizer(BaseOptimizer):
    """
    NSGA-II（Non-dominated Sorting Genetic Algorithm II）优化器
    非支配排序遗传算法
    """

    def __init__(
        self,
        objectives: List,
        constraints: List = None,
        n_candidates: int = 1000,
        n_samples: int = 20,
        random_seed: int = None
    ):
        """
        初始化NSGA-II优化器

        Args:
            objectives: 目标函数列表
            constraints: 约束条件列表
            n_candidates: 候选点数量
            n_samples: 采样点数量
            random_seed: 随机种子
        """
        super().__init__(objectives, constraints, n_candidates, n_samples, random_seed)

    def optimize(
        self,
        population_size: int = 100,
        n_generations: int = 100,
        crossover_prob: float = 0.9,
        mutation_prob: float = 0.1,
        verbose: bool = False
    ) -> Population:
        """
        执行NSGA-II优化

        Args:
            population_size: 种群规模
            n_generations: 进化代数
            crossover_prob: 交叉概率
            mutation_prob: 变异概率
            verbose: 是否输出进度信息

        Returns:
            Population: 优化后的种群
        """
        # 验证输入
        self.validate_input()

        start_time = time.time()

        # 初始化种群
        if verbose:
            print(f"初始化种群，规模: {population_size}")

        population = self.initialize_population(population_size)

        # 进化循环
        for gen in range(n_generations):
            # 生成子代
            offspring = self._generate_offspring(
                population,
                crossover_prob,
                mutation_prob
            )

            # 评估子代
            for child in offspring:
                self.evaluate_individual(child)

            # 合并种群
            combined = self._merge_populations(population, offspring)

            # 选择下一代
            population = self._select_next_generation(combined, population_size)
            population.generation = gen + 1

            # 记录收敛历史
            self.record_convergence(gen, population)

            # 输出进度
            if verbose and (gen % 10 == 0 or gen == n_generations - 1):
                elapsed = time.time() - start_time
                stats = population.get_statistics()
                print(f"代数: {gen+1}/{n_generations}, "
                      f"帕累托规模: {stats['pareto_size']}, "
                      f"可行解: {stats['n_feasible']}, "
                      f"耗时: {elapsed:.2f}s")

        total_time = time.time() - start_time

        if verbose:
            print(f"优化完成，总耗时: {total_time:.2f}s")
            print(f"帕累托前沿规模: {len(population.get_pareto_front())}")

        # 在种群元数据中保存优化统计信息
        population.metadata = {
            'total_time': total_time,
            'n_generations': n_generations,
            'population_size': population_size,
            'crossover_prob': crossover_prob,
            'mutation_prob': mutation_prob,
        }

        return population

    def _generate_offspring(
        self,
        population: Population,
        crossover_prob: float,
        mutation_prob: float
    ) -> List[Individual]:
        """
        生成子代个体

        Args:
            population: 父代种群
            crossover_prob: 交叉概率
            mutation_prob: 变异概率

        Returns:
            List[Individual]: 子代个体列表
        """
        offspring = []

        while len(offspring) < population.size:
            # 锦标赛选择
            parent1 = self._tournament_selection(population)
            parent2 = self._tournament_selection(population)

            # 交叉
            child1, child2 = self._crossover(parent1, parent2, crossover_prob)

            # 变异
            child1 = self._mutation(child1, mutation_prob)
            child2 = self._mutation(child2, mutation_prob)

            offspring.extend([child1, child2])

        return offspring[:population.size]

    def _tournament_selection(
        self,
        population: Population,
        tournament_size: int = 2
    ) -> Individual:
        """
        锦标赛选择

        Args:
            population: 种群
            tournament_size: 锦标赛规模

        Returns:
            Individual: 被选中的个体
        """
        # 随机选择tournament_size个个体
        indices = np.random.choice(len(population), tournament_size, replace=False)
        candidates = [population.individuals[i] for i in indices]

        # 选择最优个体（比较rank和crowding_distance）
        best = candidates[0]
        for candidate in candidates[1:]:
            if self._is_better(candidate, best):
                best = candidate

        return best

    def _is_better(self, ind1: Individual, ind2: Individual) -> bool:
        """
        比较两个个体的优劣

        Args:
            ind1: 个体1
            ind2: 个体2

        Returns:
            bool: 如果ind1优于ind2返回True
        """
        # 优先比较rank
        if ind1.rank != ind2.rank:
            return ind1.rank < ind2.rank

        # rank相同时比较crowding_distance
        return ind1.crowding_distance > ind2.crowding_distance

    def _crossover(
        self,
        parent1: Individual,
        parent2: Individual,
        prob: float
    ) -> Tuple[Individual, Individual]:
        """
        交叉操作（使用部分映射交叉PMX）

        Args:
            parent1: 父代1
            parent2: 父代2
            prob: 交叉概率

        Returns:
            Tuple[Individual, Individual]: 两个子代个体
        """
        if np.random.random() > prob:
            return parent1.copy(), parent2.copy()

        n = len(parent1.genes)

        # 随机选择两个交叉点
        i, j = sorted(np.random.choice(n, 2, replace=False))

        # 创建子代
        child1 = Individual()
        child2 = Individual()
        child1.genes = parent1.genes.copy()
        child2.genes = parent2.genes.copy()

        # 交换中间段
        child1.genes[i:j] = parent2.genes[i:j]
        child2.genes[i:j] = parent1.genes[i:j]

        # 修复冲突
        child1.genes = self._resolve_conflicts(child1.genes, parent1.genes, i, j)
        child2.genes = self._resolve_conflicts(child2.genes, parent2.genes, i, j)

        return child1, child2

    def _resolve_conflicts(
        self,
        child_genes: np.ndarray,
        parent_genes: np.ndarray,
        start: int,
        end: int
    ) -> np.ndarray:
        """
        修复交叉后的基因冲突

        Args:
            child_genes: 子代基因
            parent_genes: 父代基因
            start: 交叉起始位置
            end: 交叉结束位置

        Returns:
            np.ndarray: 修复后的基因
        """
        result = child_genes.copy()

        for i in range(start, end):
            # 如果冲突，用父代基因替换
            if result[i] in parent_genes[start:end]:
                # 找到冲突的位置
                conflict_pos = np.where(parent_genes == result[i])[0][0]
                # 用父代的基因替换
                result[i] = parent_genes[conflict_pos]

        return result

    def _mutation(
        self,
        individual: Individual,
        prob: float
    ) -> Individual:
        """
        变异操作（随机替换）

        Args:
            individual: 个体
            prob: 变异概率

        Returns:
            Individual: 变异后的个体
        """
        mutated = individual.copy()
        n = len(mutated.genes)

        for i in range(n):
            if np.random.random() < prob:
                # 随机替换为新的采样点
                mutated.genes[i] = np.random.randint(0, self.n_candidates)

        return mutated

    def _merge_populations(
        self,
        pop1: Population,
        pop2
    ) -> Population:
        """
        合并两个种群

        Args:
            pop1: 种群1
            pop2: 种群2（Population 或 Individual 列表）

        Returns:
            Population: 合并后的种群
        """
        merged = Population()
        if isinstance(pop2, Population):
            pop2_individuals = pop2.individuals
        else:
            pop2_individuals = list(pop2)

        merged.individuals = pop1.individuals + pop2_individuals
        merged.size = len(merged.individuals)
        return merged

    def _select_next_generation(
        self,
        population: Population,
        target_size: int
    ) -> Population:
        """
        选择下一代种群

        Args:
            population: 当前种群
            target_size: 目标规模

        Returns:
            Population: 下一代种群
        """
        # 非支配排序
        fronts = self._fast_non_dominated_sort(population)
        population.fronts = fronts

        # 计算拥挤度
        for front in fronts:
            self._calculate_crowding_distance(front, population)

        # 选择个体
        next_pop = Population()
        current_rank = 0

        while current_rank < len(fronts) and len(next_pop) + len(fronts[current_rank]) <= target_size:
            for idx in fronts[current_rank]:
                next_pop.add_individual(population.individuals[idx])
            current_rank += 1

        # 如果最后一前沿个体超过剩余名额，按拥挤度选择
        if len(next_pop) < target_size and current_rank < len(fronts):
            remaining = target_size - len(next_pop)
            sorted_front = sorted(
                fronts[current_rank],
                key=lambda i: population.individuals[i].crowding_distance,
                reverse=True
            )
            for idx in sorted_front[:remaining]:
                next_pop.add_individual(population.individuals[idx])

        # 兼容下游接口：保持 fronts/rank/crowding_distance 可用
        next_pop.fronts = self._fast_non_dominated_sort(next_pop)
        for front in next_pop.fronts:
            self._calculate_crowding_distance(front, next_pop)

        return next_pop

    def _fast_non_dominated_sort(self, population: Population) -> List[List[int]]:
        """
        快速非支配排序

        Args:
            population: 种群

        Returns:
            List[List[int]]: 各前沿面的索引列表
        """
        fronts = [[]]
        domination_count = [0] * population.size
        dominated_solutions = [[] for _ in range(population.size)]

        for i in range(population.size):
            for j in range(population.size):
                if population.individuals[i].dominates(population.individuals[j]):
                    dominated_solutions[i].append(j)
                elif population.individuals[j].dominates(population.individuals[i]):
                    domination_count[i] += 1

            if domination_count[i] == 0:
                population.individuals[i].rank = 0
                fronts[0].append(i)

        k = 0
        while len(fronts[k]) > 0:
            next_front = []
            for i in fronts[k]:
                for j in dominated_solutions[i]:
                    domination_count[j] -= 1
                    if domination_count[j] == 0:
                        population.individuals[j].rank = k + 1
                        next_front.append(j)
            k += 1
            fronts.append(next_front)

        return fronts[:-1]  # 移除最后一个空列表

    def _calculate_crowding_distance(self, front: List[int], population: Population):
        """
        计算前沿面的拥挤度

        Args:
            front: 前沿面索引列表
            population: 种群
        """
        if len(front) == 0:
            return

        # 初始化拥挤度
        for i in front:
            population.individuals[i].crowding_distance = 0

        # 边界点拥挤度设为无穷大
        if len(front) == 1:
            population.individuals[front[0]].crowding_distance = float('inf')
            return

        if len(front) == 2:
            population.individuals[front[0]].crowding_distance = float('inf')
            population.individuals[front[1]].crowding_distance = float('inf')
            return

        # 计算每个目标函数的拥挤度
        num_objectives = len(population.individuals[front[0]].objectives)

        for m in range(num_objectives):
            # 按目标m排序
            sorted_front = sorted(front, key=lambda i: population.individuals[i].objectives[m])

            # 边界点拥挤度设为无穷大
            population.individuals[sorted_front[0]].crowding_distance = float('inf')
            population.individuals[sorted_front[-1]].crowding_distance = float('inf')

            # 计算中间点的拥挤度
            obj_min = population.individuals[sorted_front[0]].objectives[m]
            obj_max = population.individuals[sorted_front[-1]].objectives[m]
            obj_range = obj_max - obj_min

            if obj_range == 0:
                continue

            for i in range(1, len(sorted_front) - 1):
                if population.individuals[sorted_front[i]].crowding_distance != float('inf'):
                    distance = (population.individuals[sorted_front[i+1]].objectives[m] -
                               population.individuals[sorted_front[i-1]].objectives[m])
                    population.individuals[sorted_front[i]].crowding_distance += distance / obj_range
