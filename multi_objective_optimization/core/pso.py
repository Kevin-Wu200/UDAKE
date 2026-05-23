"""
粒子群优化算法实现
Particle Swarm Optimization (PSO) Algorithm

用于变异函数参数优化、采样点布局优化等场景。
支持标准PSO、惯性权重自适应PSO、带约束PSO。
"""

import numpy as np
from typing import List, Dict, Any, Optional, Callable, Tuple
import time
from .optimizer import BaseOptimizer
from .population import Population, Individual


class Particle:
    """PSO粒子"""

    def __init__(self, position: np.ndarray, velocity: np.ndarray):
        self.position = position.copy()
        self.velocity = velocity.copy()
        self.best_position = position.copy()
        self.best_fitness = float('inf')
        self.current_fitness = float('inf')

    def copy(self) -> 'Particle':
        p = Particle(self.position, self.velocity)
        p.best_position = self.best_position.copy()
        p.best_fitness = self.best_fitness
        p.current_fitness = self.current_fitness
        return p


class PSOOptimizer:
    """
    粒子群优化器

    支持场景：
    - 变异函数参数优化（sill, range, nugget, model_type选择）
    - 采样点布局优化
    - 权重参数调优
    - 一般连续/离散参数优化

    特性：
    - 惯性权重线性递减
    - 速度钳制
    - 边界处理（反射/吸收）
    - 早停机制
    - 收敛历史追踪
    """

    def __init__(
        self,
        n_particles: int = 30,
        n_iterations: int = 100,
        inertia_weight: float = 0.7,
        cognitive_weight: float = 1.5,
        social_weight: float = 1.5,
        min_inertia: float = 0.4,
        velocity_clamp: Optional[float] = None,
        random_seed: Optional[int] = None,
        early_stopping_rounds: int = 20,
        early_stopping_tol: float = 1e-6,
    ):
        """
        初始化PSO优化器

        Args:
            n_particles: 粒子数量
            n_iterations: 最大迭代次数
            inertia_weight: 初始惯性权重
            cognitive_weight: 认知权重（个体最优吸引力）
            social_weight: 社会权重（全局最优吸引力）
            min_inertia: 最小惯性权重（线性递减终点）
            velocity_clamp: 速度钳制阈值，None则自动计算
            random_seed: 随机种子
            early_stopping_rounds: 早停连续轮次
            early_stopping_tol: 早停容忍度
        """
        self.n_particles = n_particles
        self.n_iterations = n_iterations
        self.inertia_weight = inertia_weight
        self.cognitive_weight = cognitive_weight
        self.social_weight = social_weight
        self.min_inertia = min_inertia
        self.velocity_clamp = velocity_clamp
        self.early_stopping_rounds = early_stopping_rounds
        self.early_stopping_tol = early_stopping_tol

        if random_seed is not None:
            np.random.seed(random_seed)

        # 运行时状态
        self.particles: List[Particle] = []
        self.global_best_position: Optional[np.ndarray] = None
        self.global_best_fitness: float = float('inf')
        self.convergence_history: List[Dict[str, Any]] = []
        self._iteration: int = 0

    def optimize(
        self,
        fitness_func: Callable[[np.ndarray], float],
        bounds: List[Tuple[float, float]],
        discrete_indices: Optional[List[int]] = None,
        discrete_values: Optional[List[List[Any]]] = None,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        执行PSO优化

        Args:
            fitness_func: 适应度函数，输入位置向量，输出适应度值（越小越好）
            bounds: 每个维度的边界 [(min, max), ...]
            discrete_indices: 离散维度的索引列表
            discrete_values: 每个离散维度的可选值列表
            verbose: 是否输出进度

        Returns:
            Dict: 包含最优解和收敛历史的字典
            {
                'best_position': np.ndarray,
                'best_fitness': float,
                'convergence_history': List[Dict],
                'n_iterations': int,
                'total_time': float,
            }
        """
        n_dims = len(bounds)
        start_time = time.time()

        # 自动计算速度钳制
        if self.velocity_clamp is None:
            ranges = np.array([b[1] - b[0] for b in bounds])
            self.velocity_clamp = float(0.2 * np.max(ranges))

        # 初始化粒子
        self._initialize_particles(n_dims, bounds, fitness_func, discrete_indices, discrete_values)

        # 早停变量
        best_stable_count = 0
        prev_best = float('inf')

        for iteration in range(self.n_iterations):
            self._iteration = iteration

            # 计算当前惯性权重（线性递减）
            w = self.inertia_weight - (self.inertia_weight - self.min_inertia) * (iteration / self.n_iterations)

            # 更新每个粒子
            for particle in self.particles:
                # 生成随机系数
                r1 = np.random.random(n_dims)
                r2 = np.random.random(n_dims)

                # 速度更新
                cognitive = self.cognitive_weight * r1 * (particle.best_position - particle.position)
                social = self.social_weight * r2 * (self.global_best_position - particle.position)
                particle.velocity = w * particle.velocity + cognitive + social

                # 速度钳制
                particle.velocity = np.clip(particle.velocity, -self.velocity_clamp, self.velocity_clamp)

                # 位置更新
                particle.position = particle.position + particle.velocity

                # 边界处理（反射策略）
                particle.position = self._handle_bounds(particle.position, bounds)

                # 离散维度取整
                if discrete_indices:
                    for idx in discrete_indices:
                        if idx < n_dims:
                            if discrete_values and idx < len(discrete_values):
                                # 取最近的有效离散值
                                vals = discrete_values[idx]
                                particle.position[idx] = min(vals, key=lambda v: abs(v - particle.position[idx]))
                            else:
                                particle.position[idx] = round(particle.position[idx])
                                particle.position[idx] = np.clip(particle.position[idx], bounds[idx][0], bounds[idx][1])

                # 评估适应度
                particle.current_fitness = fitness_func(particle.position)

                # 更新个体最优
                if particle.current_fitness < particle.best_fitness:
                    particle.best_fitness = particle.current_fitness
                    particle.best_position = particle.position.copy()

                # 更新全局最优
                if particle.current_fitness < self.global_best_fitness:
                    self.global_best_fitness = particle.current_fitness
                    self.global_best_position = particle.position.copy()

            # 记录收敛历史
            avg_fitness = float(np.mean([p.current_fitness for p in self.particles]))
            best_fitness = self.global_best_fitness

            self.convergence_history.append({
                'iteration': iteration,
                'best_fitness': best_fitness,
                'avg_fitness': avg_fitness,
                'inertia_weight': w,
            })

            # 早停检查
            if abs(prev_best - best_fitness) < self.early_stopping_tol:
                best_stable_count += 1
            else:
                best_stable_count = 0
            prev_best = best_fitness

            if best_stable_count >= self.early_stopping_rounds:
                if verbose:
                    print(f"PSO早停于迭代 {iteration + 1}，最优适应度: {best_fitness:.6f}")
                break

            if verbose and (iteration % 10 == 0 or iteration == self.n_iterations - 1):
                print(f"PSO迭代 {iteration + 1}/{self.n_iterations}, "
                      f"最优: {best_fitness:.6f}, 平均: {avg_fitness:.6f}, w: {w:.4f}")

        total_time = time.time() - start_time

        if verbose:
            print(f"PSO优化完成，总耗时: {total_time:.2f}s，最优适应度: {self.global_best_fitness:.6f}")

        return {
            'best_position': self.global_best_position,
            'best_fitness': self.global_best_fitness,
            'convergence_history': self.convergence_history,
            'n_iterations': len(self.convergence_history),
            'total_time': total_time,
        }

    def _initialize_particles(
        self,
        n_dims: int,
        bounds: List[Tuple[float, float]],
        fitness_func: Callable,
        discrete_indices: Optional[List[int]],
        discrete_values: Optional[List[List[Any]]],
    ) -> None:
        """初始化粒子群"""
        self.particles = []
        self.global_best_fitness = float('inf')
        self.global_best_position = None
        self.convergence_history = []

        for _ in range(self.n_particles):
            # 随机初始化位置
            position = np.array([np.random.uniform(b[0], b[1]) for b in bounds])

            # 离散维度处理
            if discrete_indices:
                for idx in discrete_indices:
                    if idx < n_dims:
                        if discrete_values and idx < len(discrete_values):
                            vals = discrete_values[idx]
                            position[idx] = float(np.random.choice(vals))
                        else:
                            position[idx] = float(np.random.randint(int(bounds[idx][0]), int(bounds[idx][1]) + 1))

            # 初始化速度
            velocity = np.random.uniform(-1, 1, n_dims) * 0.1
            for i, b in enumerate(bounds):
                velocity[i] *= (b[1] - b[0]) * 0.1

            particle = Particle(position, velocity)
            particle.current_fitness = fitness_func(position)
            particle.best_fitness = particle.current_fitness
            particle.best_position = position.copy()

            self.particles.append(particle)

            if particle.current_fitness < self.global_best_fitness:
                self.global_best_fitness = particle.current_fitness
                self.global_best_position = position.copy()

    def _handle_bounds(self, position: np.ndarray, bounds: List[Tuple[float, float]]) -> np.ndarray:
        """边界处理：反射策略"""
        pos = position.copy()
        for i, (low, high) in enumerate(bounds):
            if pos[i] < low:
                pos[i] = low + (low - pos[i])  # 反射
                if pos[i] > high:
                    pos[i] = (low + high) / 2  # 反弹到中心
            elif pos[i] > high:
                pos[i] = high - (pos[i] - high)  # 反射
                if pos[i] < low:
                    pos[i] = (low + high) / 2
        return pos

    def optimize_variogram_params(
        self,
        distances: np.ndarray,
        empirical_variogram: np.ndarray,
        model_types: Optional[List[str]] = None,
        param_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """
        使用PSO优化变异函数参数

        Args:
            distances: 距离数组
            empirical_variogram: 经验变异函数值数组
            model_types: 候选模型类型列表，默认 ['spherical', 'exponential', 'gaussian', 'power']
            param_bounds: 参数边界 {'sill': (0, max), 'range': (0, max), 'nugget': (0, max), 'power': (0, 2)}
            verbose: 是否输出进度

        Returns:
            Dict: 最优参数和模型信息
        """
        if model_types is None:
            model_types = ['spherical', 'exponential', 'gaussian', 'power']

        if param_bounds is None:
            max_semivar = float(np.max(empirical_variogram)) * 1.5
            max_dist = float(np.max(distances)) * 1.5
            param_bounds = {
                'sill': (0.01, max_semivar),
                'range': (1.0, max_dist),
                'nugget': (0.0, max_semivar * 0.5),
                'power': (0.1, 2.0),
            }

        best_result = None
        best_aic = float('inf')
        n_points = len(distances)

        for model_type in model_types:
            # 构建边界
            bounds = [
                param_bounds['sill'],
                param_bounds['range'],
                param_bounds['nugget'],
            ]

            if model_type == 'power':
                bounds.append(param_bounds['power'])

            def make_fitness(model_type: str) -> Callable:
                def fitness(position: np.ndarray) -> float:
                    sill, range_val, nugget = position[0], position[1], position[2]
                    power_val = position[3] if len(position) > 3 else 1.0

                    # 计算理论变异函数值
                    h = distances / range_val
                    h = np.clip(h, 0, None)

                    if model_type == 'spherical':
                        theoretical = np.where(h <= 1, sill * (1.5 * h - 0.5 * h**3), sill) + nugget
                    elif model_type == 'exponential':
                        theoretical = sill * (1 - np.exp(-3 * h)) + nugget
                    elif model_type == 'gaussian':
                        theoretical = sill * (1 - np.exp(-3 * h**2)) + nugget
                    elif model_type == 'power':
                        theoretical = sill * (h ** power_val) + nugget
                    else:
                        theoretical = sill * (1 - np.exp(-3 * h)) + nugget

                    # 加权RMSE
                    weights = 1.0 / (distances + 1e-6)
                    rmse = float(np.sqrt(np.mean(weights * (empirical_variogram - theoretical) ** 2)))

                    # AIC惩罚项
                    n_params = 3 if model_type != 'power' else 4
                    aic_penalty = 2 * n_params / n_points if n_points > 0 else 0
                    return rmse + aic_penalty
                return fitness

            fitness_func = make_fitness(model_type)
            result = self.optimize(fitness_func, bounds, verbose=verbose)

            # 计算AIC
            final_fitness = result['best_fitness']
            n_params = 3 if model_type != 'power' else 4
            aic = n_points * np.log(final_fitness + 1e-10) + 2 * n_params

            if aic < best_aic:
                best_aic = aic
                best_result = {
                    'model_type': model_type,
                    'sill': float(result['best_position'][0]),
                    'range': float(result['best_position'][1]),
                    'nugget': float(result['best_position'][2]),
                    'power': float(result['best_position'][3]) if model_type == 'power' else None,
                    'rmse': float(final_fitness),
                    'aic': float(aic),
                    'convergence_history': result['convergence_history'],
                    'n_iterations': result['n_iterations'],
                    'total_time': result['total_time'],
                }

        return best_result


class PSOMultiObjectiveOptimizer(BaseOptimizer):
    """
    基于PSO的多目标优化器

    使用加权和法将多目标转化为单目标进行PSO优化。
    兼容BaseOptimizer接口，可与NSGA-II互换使用。
    """

    def __init__(
        self,
        objectives: List,
        constraints: List = None,
        n_candidates: int = 1000,
        n_samples: int = 20,
        random_seed: Optional[int] = None,
        objective_weights: Optional[np.ndarray] = None,
        n_particles: int = 50,
        n_iterations: int = 200,
    ):
        super().__init__(objectives, constraints, n_candidates, n_samples, random_seed)
        self.objective_weights = objective_weights
        self.n_particles = n_particles
        self.n_iterations = n_iterations
        self._pso_optimizer: Optional[PSOOptimizer] = None

    def optimize(
        self,
        population_size: int = 100,
        n_generations: int = 100,
        verbose: bool = False,
        **kwargs,
    ) -> Population:
        """
        执行PSO多目标优化

        Args:
            population_size: 种群规模（PSO中对应粒子数，两者取较大值）
            n_generations: 进化代数（PSO中对应迭代次数，两者取较大值）
            verbose: 是否输出进度

        Returns:
            Population: 优化后的种群
        """
        self.validate_input()

        # 使用粒子数和迭代次数
        effective_particles = max(self.n_particles, population_size)
        effective_iterations = max(self.n_iterations, n_generations)

        # 确定目标权重
        if self.objective_weights is None:
            self.objective_weights = np.ones(len(self.objectives)) / len(self.objectives)

        # 边界：每个基因维度对应候选点索引
        bounds = [(0, self.n_candidates - 1) for _ in range(self.n_samples)]
        discrete_indices = list(range(self.n_samples))

        # 构建加权适应度函数
        def weighted_fitness(genes: np.ndarray) -> float:
            individual = Individual()
            individual.genes = genes.astype(int)
            individual = self.evaluate_individual(individual)
            return float(np.dot(individual.objectives, self.objective_weights))

        # 执行PSO
        self._pso_optimizer = PSOOptimizer(
            n_particles=effective_particles,
            n_iterations=effective_iterations,
            random_seed=None,
        )
        result = self._pso_optimizer.optimize(
            weighted_fitness,
            bounds,
            discrete_indices=discrete_indices,
            verbose=verbose,
        )

        # 构建结果种群
        population = Population()
        best_individual = Individual()
        best_individual.genes = result['best_position'].astype(int)
        best_individual = self.evaluate_individual(best_individual)
        best_individual.rank = 0
        best_individual.crowding_distance = float('inf')
        population.add_individual(best_individual)

        # 补充一些次优解（粒子群的历史最优）
        if self._pso_optimizer and self._pso_optimizer.particles:
            # 按个体最优排序取top解
            sorted_particles = sorted(self._pso_optimizer.particles, key=lambda p: p.best_fitness)
            for particle in sorted_particles[:population_size - 1]:
                ind = Individual()
                ind.genes = particle.best_position.astype(int)
                # 确保不重复
                if not any(np.array_equal(ind.genes, pop.genes) for pop in population.individuals):
                    ind = self.evaluate_individual(ind)
                    population.add_individual(ind)

        population.generation = effective_iterations
        population.metadata = {
            'total_time': result['total_time'],
            'n_iterations': result['n_iterations'],
            'n_particles': effective_particles,
            'optimizer': 'PSO',
        }

        self.convergence_history = self._pso_optimizer.convergence_history
        return population
