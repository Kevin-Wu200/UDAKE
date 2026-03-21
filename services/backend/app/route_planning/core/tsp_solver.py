"""
旅行商问题（TSP）求解器
实现多种TSP求解算法
"""

import random
import math
from typing import List, Tuple, Dict, Optional
from abc import ABC, abstractmethod
import time


class TSPSolver(ABC):
    """TSP求解器基类"""

    def __init__(self, distance_matrix: List[List[float]]):
        """
        初始化TSP求解器

        Args:
            distance_matrix: 距离矩阵
        """
        self.distance_matrix = distance_matrix
        self.num_cities = len(distance_matrix)

    @abstractmethod
    def solve(self, start_city: int = 0) -> Tuple[List[int], float]:
        """
        求解TSP

        Args:
            start_city: 起始城市索引

        Returns:
            (路径列表, 总距离)
        """
        pass

    def calculate_total_distance(self, path: List[int]) -> float:
        """
        计算路径总距离

        Args:
            path: 路径列表

        Returns:
            总距离
        """
        total = 0
        for i in range(len(path) - 1):
            total += self.distance_matrix[path[i]][path[i + 1]]
        return total


class GreedyTSPSolver(TSPSolver):
    """贪婪TSP求解器"""

    def solve(self, start_city: int = 0) -> Tuple[List[int], float]:
        """
        使用贪婪算法求解TSP
        每次选择最近的未访问城市

        Args:
            start_city: 起始城市索引

        Returns:
            (路径列表, 总距离)
        """
        path = [start_city]
        unvisited = set(range(self.num_cities))
        unvisited.remove(start_city)

        current = start_city

        while unvisited:
            # 找到最近的未访问城市
            nearest = min(unvisited, key=lambda city: self.distance_matrix[current][city])
            path.append(nearest)
            unvisited.remove(nearest)
            current = nearest

        # 返回起点
        path.append(start_city)

        total_distance = self.calculate_total_distance(path)
        return path, total_distance


class NearestNeighborTSPSolver(TSPSolver):
    """最近邻TSP求解器"""

    def solve(self, start_city: int = 0) -> Tuple[List[int], float]:
        """
        使用最近邻算法求解TSP

        Args:
            start_city: 起始城市索引

        Returns:
            (路径列表, 总距离)
        """
        path = [start_city]
        unvisited = set(range(self.num_cities))
        unvisited.remove(start_city)

        current = start_city

        while unvisited:
            # 找到最近的未访问城市
            nearest = min(unvisited, key=lambda city: self.distance_matrix[current][city])
            path.append(nearest)
            unvisited.remove(nearest)
            current = nearest

        # 返回起点
        path.append(start_city)

        total_distance = self.calculate_total_distance(path)
        return path, total_distance


class TwoOptTSPSolver(TSPSolver):
    """2-opt局部搜索TSP求解器"""

    def __init__(self, distance_matrix: List[List[float]], max_iterations: int = 1000):
        """
        初始化2-opt求解器

        Args:
            distance_matrix: 距离矩阵
            max_iterations: 最大迭代次数
        """
        super().__init__(distance_matrix)
        self.max_iterations = max_iterations

    def solve(self, start_city: int = 0) -> Tuple[List[int], float]:
        """
        使用2-opt算法求解TSP

        Args:
            start_city: 起始城市索引

        Returns:
            (路径列表, 总距离)
        """
        # 先用最近邻算法获得初始解
        nn_solver = NearestNeighborTSPSolver(self.distance_matrix)
        path, _ = nn_solver.solve(start_city)

        improved = True
        iterations = 0

        while improved and iterations < self.max_iterations:
            improved = False
            iterations += 1

            for i in range(1, len(path) - 2):
                for j in range(i + 1, len(path) - 1):
                    # 尝试交换边
                    new_path = self._two_opt_swap(path, i, j)
                    new_distance = self.calculate_total_distance(new_path)

                    if new_distance < self.calculate_total_distance(path):
                        path = new_path
                        improved = True

        total_distance = self.calculate_total_distance(path)
        return path, total_distance

    @staticmethod
    def _two_opt_swap(path: List[int], i: int, j: int) -> List[int]:
        """
        执行2-opt交换

        Args:
            path: 原始路径
            i: 第一个索引
            j: 第二个索引

        Returns:
            新路径
        """
        new_path = path[:i]
        new_path.extend(reversed(path[i:j+1]))
        new_path.extend(path[j+1:])
        return new_path


class SimulatedAnnealingTSPSolver(TSPSolver):
    """模拟退火TSP求解器"""

    def __init__(self,
                 distance_matrix: List[List[float]],
                 initial_temperature: float = 1000.0,
                 cooling_rate: float = 0.995,
                 min_temperature: float = 0.01):
        """
        初始化模拟退火求解器

        Args:
            distance_matrix: 距离矩阵
            initial_temperature: 初始温度
            cooling_rate: 降温速率
            min_temperature: 最小温度
        """
        super().__init__(distance_matrix)
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
        self.min_temperature = min_temperature

    def solve(self, start_city: int = 0) -> Tuple[List[int], float]:
        """
        使用模拟退火算法求解TSP

        Args:
            start_city: 起始城市索引

        Returns:
            (路径列表, 总距离)
        """
        # 先用最近邻算法获得初始解
        nn_solver = NearestNeighborTSPSolver(self.distance_matrix)
        current_path, current_distance = nn_solver.solve(start_city)

        best_path = current_path[:]
        best_distance = current_distance

        temperature = self.initial_temperature

        while temperature > self.min_temperature:
            # 生成新解（随机交换两个城市）
            new_path = current_path[:]
            i, j = random.sample(range(1, len(new_path) - 1), 2)
            new_path[i], new_path[j] = new_path[j], new_path[i]

            new_distance = self.calculate_total_distance(new_path)

            # 决定是否接受新解
            delta = new_distance - current_distance
            if delta < 0 or random.random() < math.exp(-delta / temperature):
                current_path = new_path
                current_distance = new_distance

                # 更新最优解
                if current_distance < best_distance:
                    best_path = current_path[:]
                    best_distance = current_distance

            # 降温
            temperature *= self.cooling_rate

        return best_path, best_distance


class GeneticAlgorithmTSPSolver(TSPSolver):
    """遗传算法TSP求解器"""

    def __init__(self,
                 distance_matrix: List[List[float]],
                 population_size: int = 50,
                 generations: int = 100,
                 mutation_rate: float = 0.01,
                 elite_size: int = 2):
        """
        初始化遗传算法求解器

        Args:
            distance_matrix: 距离矩阵
            population_size: 种群大小
            generations: 迭代代数
            mutation_rate: 变异率
            elite_size: 精英个体数量
        """
        super().__init__(distance_matrix)
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size

    def solve(self, start_city: int = 0) -> Tuple[List[int], float]:
        """
        使用遗传算法求解TSP

        Args:
            start_city: 起始城市索引

        Returns:
            (路径列表, 总距离)
        """
        # 初始化种群
        population = self._create_population(start_city)

        for generation in range(self.generations):
            # 评估适应度
            ranked_population = self._rank_population(population)

            # 选择
            selection_results = self._selection(ranked_population)

            # 交叉
            breeding_pool = selection_results[self.elite_size:]
            children = self._crossover(breeding_pool)

            # 变异
            mutated_population = self._mutate(children)

            # 更新种群（保留精英）
            population = selection_results[:self.elite_size] + mutated_population

        # 返回最优解
        best_path = min(population, key=lambda x: self.calculate_total_distance(x))
        best_distance = self.calculate_total_distance(best_path)

        return best_path, best_distance

    def _create_population(self, start_city: int) -> List[List[int]]:
        """创建初始种群"""
        population = []
        for _ in range(self.population_size):
            path = list(range(self.num_cities))
            random.shuffle(path)
            # 确保起点正确
            if start_city in path:
                path.remove(start_city)
            path = [start_city] + path + [start_city]
            population.append(path)
        return population

    def _rank_population(self, population: List[List[int]]) -> List[List[int]]:
        """对种群按适应度排序"""
        return sorted(population, key=lambda x: self.calculate_total_distance(x))

    def _selection(self, ranked_population: List[List[int]]) -> List[List[int]]:
        """选择操作"""
        selection_results = []
        df = [1 / (self.calculate_total_distance(path) + 1) for path in ranked_population]
        total = sum(df)
        probs = [d / total for d in df]

        for _ in range(len(ranked_population)):
            selected = random.choices(ranked_population, weights=probs)[0]
            selection_results.append(selected)

        return selection_results

    def _crossover(self, breeding_pool: List[List[int]]) -> List[List[int]]:
        """交叉操作"""
        children = []
        for i in range(0, len(breeding_pool) - 1, 2):
            parent1 = breeding_pool[i]
            parent2 = breeding_pool[i + 1]
            child1, child2 = self._order_crossover(parent1, parent2)
            children.append(child1)
            children.append(child2)
        return children

    @staticmethod
    def _order_crossover(parent1: List[int], parent2: List[int]) -> Tuple[List[int], List[int]]:
        """顺序交叉"""
        size = len(parent1)
        start, end = sorted(random.sample(range(1, size - 1), 2))

        child1 = [None] * size
        child2 = [None] * size

        # 复制父代片段
        child1[start:end+1] = parent1[start:end+1]
        child2[start:end+1] = parent2[start:end+1]

        # 填充剩余基因
        def fill_child(child, parent):
            filled = set(child[start:end+1])
            idx = (end + 1) % size
            for gene in parent:
                if gene not in filled:
                    child[idx] = gene
                    idx = (idx + 1) % size
            return child

        child1 = fill_child(child1, parent2)
        child2 = fill_child(child2, parent1)

        return child1, child2

    def _mutate(self, population: List[List[int]]) -> List[List[int]]:
        """变异操作"""
        mutated = []
        for individual in population:
            if random.random() < self.mutation_rate:
                # 随机交换两个城市
                i, j = random.sample(range(1, len(individual) - 1), 2)
                individual[i], individual[j] = individual[j], individual[i]
            mutated.append(individual)
        return mutated