"""
蚁群优化算法（ACO）实现
用于解决TSP等组合优化问题
"""

import random
from typing import Dict, List, Tuple

import numpy as np


class ACOAlgorithm:
    """蚁群优化算法"""

    def __init__(self,
                 distance_matrix: List[List[float]],
                 num_ants: int = 20,
                 alpha: float = 1.0,
                 beta: float = 2.0,
                 rho: float = 0.5,
                 q: float = 1.0,
                 max_iterations: int = 100):
        """
        初始化ACO算法

        Args:
            distance_matrix: 距离矩阵
            num_ants: 蚂蚁数量
            alpha: 信息素重要性因子
            beta: 启发信息重要性因子
            rho: 信息素挥发率
            q: 信息素强度因子
            max_iterations: 最大迭代次数
        """
        self.distance_matrix = np.array(distance_matrix)
        self.num_cities = len(distance_matrix)
        self.num_ants = num_ants
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q = q
        self.max_iterations = max_iterations

        # 初始化信息素矩阵
        self.pheromone = np.ones((self.num_cities, self.num_cities)) / self.num_cities

        # 初始化启发信息（距离的倒数）
        self.heuristic = np.zeros((self.num_cities, self.num_cities))
        for i in range(self.num_cities):
            for j in range(self.num_cities):
                if i != j and self.distance_matrix[i][j] > 0:
                    self.heuristic[i][j] = 1.0 / self.distance_matrix[i][j]

    def solve(self, start_city: int = 0) -> Tuple[List[int], float]:
        """
        使用ACO算法求解TSP

        Args:
            start_city: 起始城市索引

        Returns:
            (最优路径, 最优距离)
        """
        best_path = None
        best_distance = float('inf')

        for iteration in range(self.max_iterations):
            # 构建蚂蚁路径
            all_paths = []
            all_distances = []

            for ant in range(self.num_ants):
                path = self._construct_path(start_city)
                distance = self._calculate_distance(path)
                all_paths.append(path)
                all_distances.append(distance)

                # 更新最优解
                if distance < best_distance:
                    best_distance = distance
                    best_path = path

            # 更新信息素
            self._update_pheromone(all_paths, all_distances)

        return best_path, best_distance

    def _construct_path(self, start_city: int) -> List[int]:
        """
        构建单个蚂蚁的路径

        Args:
            start_city: 起始城市

        Returns:
            路径列表
        """
        path = [start_city]
        visited = set([start_city])
        current_city = start_city

        while len(visited) < self.num_cities:
            # 选择下一个城市
            next_city = self._select_next_city(current_city, visited)
            path.append(next_city)
            visited.add(next_city)
            current_city = next_city

        # 返回起点
        path.append(start_city)

        return path

    def _select_next_city(self, current_city: int, visited: set) -> int:
        """
        根据信息素和启发信息选择下一个城市

        Args:
            current_city: 当前城市
            visited: 已访问城市集合

        Returns:
            下一个城市索引
        """
        unvisited = [city for city in range(self.num_cities) if city not in visited]

        # 计算转移概率
        probabilities = []
        for city in unvisited:
            tau = self.pheromone[current_city][city] ** self.alpha
            eta = self.heuristic[current_city][city] ** self.beta
            probabilities.append(tau * eta)

        total = sum(probabilities)
        probabilities = [p / total for p in probabilities]

        # 轮盘赌选择
        return random.choices(unvisited, weights=probabilities, k=1)[0]

    def _calculate_distance(self, path: List[int]) -> float:
        """
        计算路径总距离

        Args:
            path: 路径列表

        Returns:
            总距离
        """
        total_distance = 0
        for i in range(len(path) - 1):
            total_distance += self.distance_matrix[path[i]][path[i + 1]]
        return total_distance

    def _update_pheromone(self, paths: List[List[int]], distances: List[float]):
        """
        更新信息素矩阵

        Args:
            paths: 所有蚂蚁的路径
            distances: 所有路径的距离
        """
        # 信息素挥发
        self.pheromone *= (1 - self.rho)

        # 信息素增强
        for path, distance in zip(paths, distances):
            delta_pheromone = self.q / distance
            for i in range(len(path) - 1):
                self.pheromone[path[i]][path[i + 1]] += delta_pheromone
                self.pheromone[path[i + 1]][path[i]] += delta_pheromone


class MultiObjectiveACO:
    """多目标蚁群优化算法"""

    def __init__(self,
                 distance_matrix: List[List[float]],
                 time_matrix: List[List[float]],
                 cost_matrix: List[List[float]],
                 num_ants: int = 20,
                 alpha: float = 1.0,
                 beta: float = 2.0,
                 rho: float = 0.5,
                 q: float = 1.0,
                 max_iterations: int = 100):
        """
        初始化多目标ACO算法

        Args:
            distance_matrix: 距离矩阵
            time_matrix: 时间矩阵
            cost_matrix: 成本矩阵
            num_ants: 蚂蚁数量
            alpha: 信息素重要性因子
            beta: 启发信息重要性因子
            rho: 信息素挥发率
            q: 信息素强度因子
            max_iterations: 最大迭代次数
        """
        self.distance_matrix = np.array(distance_matrix)
        self.time_matrix = np.array(time_matrix)
        self.cost_matrix = np.array(cost_matrix)
        self.num_cities = len(distance_matrix)
        self.num_ants = num_ants
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q = q
        self.max_iterations = max_iterations

        # 初始化信息素矩阵
        self.pheromone = np.ones((self.num_cities, self.num_cities)) / self.num_cities

        # 初始化启发信息（综合考虑距离、时间、成本）
        self.heuristic = np.zeros((self.num_cities, self.num_cities))
        for i in range(self.num_cities):
            for j in range(self.num_cities):
                if i != j and self.distance_matrix[i][j] > 0:
                    # 归一化后取平均
                    d = self.distance_matrix[i][j]
                    t = self.time_matrix[i][j]
                    c = self.cost_matrix[i][j]
                    self.heuristic[i][j] = 1.0 / (d + t + c)

    def solve(self, start_city: int = 0) -> Tuple[List[int], Dict[str, float]]:
        """
        使用多目标ACO算法求解TSP

        Args:
            start_city: 起始城市索引

        Returns:
            (最优路径, 目标值字典)
        """
        best_path = None
        best_fitness = -float('inf')

        for iteration in range(self.max_iterations):
            # 构建蚂蚁路径
            all_paths = []
            all_fitness = []

            for ant in range(self.num_ants):
                path = self._construct_path(start_city)
                fitness = self._calculate_fitness(path)
                all_paths.append(path)
                all_fitness.append(fitness)

                # 更新最优解
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_path = path

            # 更新信息素
            self._update_pheromone(all_paths, all_fitness)

        # 计算最优路径的目标值
        objectives = self._calculate_objectives(best_path)

        return best_path, objectives

    def _construct_path(self, start_city: int) -> List[int]:
        """构建单个蚂蚁的路径"""
        path = [start_city]
        visited = set([start_city])
        current_city = start_city

        while len(visited) < self.num_cities:
            next_city = self._select_next_city(current_city, visited)
            path.append(next_city)
            visited.add(next_city)
            current_city = next_city

        path.append(start_city)
        return path

    def _select_next_city(self, current_city: int, visited: set) -> int:
        """选择下一个城市"""
        unvisited = [city for city in range(self.num_cities) if city not in visited]

        probabilities = []
        for city in unvisited:
            tau = self.pheromone[current_city][city] ** self.alpha
            eta = self.heuristic[current_city][city] ** self.beta
            probabilities.append(tau * eta)

        total = sum(probabilities)
        probabilities = [p / total for p in probabilities]

        return random.choices(unvisited, weights=probabilities, k=1)[0]

    def _calculate_fitness(self, path: List[int]) -> float:
        """
        计算路径的适应度（综合考虑距离、时间、成本）

        Args:
            path: 路径列表

        Returns:
            适应度值
        """
        objectives = self._calculate_objectives(path)
        # 使用加权求和（可以根据需要调整权重）
        fitness = 1.0 / (objectives['distance'] + objectives['time'] + objectives['cost'])
        return fitness

    def _calculate_objectives(self, path: List[int]) -> Dict[str, float]:
        """
        计算路径的目标值

        Args:
            path: 路径列表

        Returns:
            目标值字典
        """
        total_distance = 0
        total_time = 0
        total_cost = 0

        for i in range(len(path) - 1):
            total_distance += self.distance_matrix[path[i]][path[i + 1]]
            total_time += self.time_matrix[path[i]][path[i + 1]]
            total_cost += self.cost_matrix[path[i]][path[i + 1]]

        return {
            'distance': total_distance,
            'time': total_time,
            'cost': total_cost
        }

    def _update_pheromone(self, paths: List[List[int]], fitness: List[float]):
        """更新信息素矩阵"""
        self.pheromone *= (1 - self.rho)

        for path, f in zip(paths, fitness):
            delta_pheromone = self.q * f
            for i in range(len(path) - 1):
                self.pheromone[path[i]][path[i + 1]] += delta_pheromone
                self.pheromone[path[i + 1]][path[i]] += delta_pheromone
