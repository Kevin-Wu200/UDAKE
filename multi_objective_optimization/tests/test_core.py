"""
核心算法测试
Core algorithm tests
"""

import unittest

import numpy as np

from multi_objective_optimization.core.nsga2 import NSGA2Optimizer
from multi_objective_optimization.core.population import Individual, Population
from multi_objective_optimization.objectives.accessibility import AccessibilityObjective
from multi_objective_optimization.objectives.cost import CostObjective
from multi_objective_optimization.objectives.variance import VarianceObjective


class TestIndividual(unittest.TestCase):
    """测试Individual类"""

    def test_initialization(self):
        """测试个体初始化"""
        ind = Individual()
        self.assertIsNotNone(ind.genes)
        self.assertIsNotNone(ind.objectives)
        self.assertEqual(ind.rank, 0)
        self.assertEqual(ind.crowding_distance, 0.0)

    def test_dominates(self):
        """测试支配关系"""
        ind1 = Individual()
        ind1.objectives = np.array([1.0, 2.0])
        ind1.is_feasible = True

        ind2 = Individual()
        ind2.objectives = np.array([2.0, 3.0])
        ind2.is_feasible = True

        # ind1应该支配ind2（更小的目标值）
        self.assertTrue(ind1.dominates(ind2))
        self.assertFalse(ind2.dominates(ind1))

    def test_copy(self):
        """测试个体拷贝"""
        ind1 = Individual()
        ind1.genes = np.array([1, 2, 3])
        ind1.objectives = np.array([1.0, 2.0])

        ind2 = ind1.copy()

        self.assertIsNot(ind1, ind2)
        np.testing.assert_array_equal(ind1.genes, ind2.genes)
        np.testing.assert_array_equal(ind1.objectives, ind2.objectives)


class TestPopulation(unittest.TestCase):
    """测试Population类"""

    def test_initialization(self):
        """测试种群初始化"""
        pop = Population(size=10)
        self.assertEqual(pop.size, 10)
        self.assertEqual(len(pop.individuals), 0)

    def test_add_individual(self):
        """测试添加个体"""
        pop = Population()
        ind = Individual()
        ind.genes = np.array([1, 2, 3])

        pop.add_individual(ind)

        self.assertEqual(pop.size, 1)
        self.assertEqual(len(pop.individuals), 1)

    def test_get_pareto_front(self):
        """测试获取帕累托前沿"""
        pop = Population()

        # 创建一些个体
        for i in range(5):
            ind = Individual()
            ind.objectives = np.array([i, i])
            ind.rank = 0 if i < 3 else 1
            pop.add_individual(ind)

        # 设置前沿
        pop.fronts = [[0, 1, 2], [3, 4]]

        pareto_front = pop.get_pareto_front()
        self.assertEqual(len(pareto_front), 3)


class TestVarianceObjective(unittest.TestCase):
    """测试VarianceObjective类"""

    def setUp(self):
        """设置测试数据"""
        self.variance_grid = np.random.rand(10, 10)
        self.x_coords = np.arange(10)
        self.y_coords = np.arange(10)

    def test_initialization(self):
        """测试初始化"""
        obj = VarianceObjective(self.variance_grid, self.x_coords, self.y_coords)
        self.assertEqual(obj.name, 'variance')
        self.assertEqual(obj.direction, 'minimize')

    def test_evaluate(self):
        """测试评估"""
        obj = VarianceObjective(self.variance_grid, self.x_coords, self.y_coords)

        ind = Individual()
        ind.genes = np.array([0, 5, 10, 15])

        variance = obj.evaluate(ind)

        self.assertIsInstance(variance, float)
        self.assertGreater(variance, 0.0)


class TestCostObjective(unittest.TestCase):
    """测试CostObjective类"""

    def test_initialization(self):
        """测试初始化"""
        obj = CostObjective(base_location=(0, 0))
        self.assertEqual(obj.name, 'cost')
        self.assertEqual(obj.direction, 'minimize')

    def test_evaluate(self):
        """测试评估"""
        obj = CostObjective(base_location=(0, 0))

        ind = Individual()
        ind.metadata = {
            'points': [(10, 10), (20, 20), (30, 30)]
        }

        cost = obj.evaluate(ind)

        self.assertIsInstance(cost, float)
        self.assertGreater(cost, 0.0)


class TestAccessibilityObjective(unittest.TestCase):
    """测试AccessibilityObjective类"""

    def test_initialization(self):
        """测试初始化"""
        obj = AccessibilityObjective()
        self.assertEqual(obj.name, 'accessibility')
        self.assertEqual(obj.direction, 'maximize')

    def test_evaluate(self):
        """测试评估"""
        obj = AccessibilityObjective(base_location=(0, 0))

        ind = Individual()
        ind.metadata = {
            'points': [(10, 10), (20, 20), (30, 30)]
        }

        accessibility = obj.evaluate(ind)

        self.assertIsInstance(accessibility, float)
        # 应该是负值（因为是最大化）
        self.assertLess(accessibility, 0.0)


class TestNSGA2Optimizer(unittest.TestCase):
    """测试NSGA2Optimizer类"""

    def setUp(self):
        """设置测试数据"""
        # 创建测试数据
        self.variance_grid = np.random.rand(20, 20)
        self.x_coords = np.arange(20)
        self.y_coords = np.arange(20)

        # 创建目标函数
        self.objectives = [
            VarianceObjective(self.variance_grid, self.x_coords, self.y_coords, weight=1.0),
            CostObjective(base_location=(0, 0), weight=1.0),
            AccessibilityObjective(base_location=(0, 0), weight=1.0),
        ]

    def test_initialization(self):
        """测试初始化"""
        optimizer = NSGA2Optimizer(
            objectives=self.objectives,
            n_candidates=400,
            n_samples=10
        )

        self.assertEqual(len(optimizer.objectives), 3)
        self.assertEqual(optimizer.n_candidates, 400)
        self.assertEqual(optimizer.n_samples, 10)

    def test_validate_input(self):
        """测试输入验证"""
        optimizer = NSGA2Optimizer(
            objectives=self.objectives,
            n_candidates=400,
            n_samples=10
        )

        # 应该通过验证
        self.assertTrue(optimizer.validate_input())

        # 测试无效输入
        optimizer.n_samples = 500  # 超过候选点数量
        with self.assertRaises(ValueError):
            optimizer.validate_input()

    def test_optimize(self):
        """测试优化过程"""
        optimizer = NSGA2Optimizer(
            objectives=self.objectives,
            n_candidates=400,
            n_samples=5,
            random_seed=42
        )

        # 运行优化（使用较小的参数以加快测试）
        result_pop = optimizer.optimize(
            population_size=20,
            n_generations=10,
            verbose=False
        )

        # 验证结果
        self.assertIsNotNone(result_pop)
        self.assertGreater(len(result_pop), 0)
        self.assertGreater(len(result_pop.get_pareto_front()), 0)

        # 验证收敛历史
        self.assertGreater(len(optimizer.convergence_history), 0)

    def test_get_best_solution(self):
        """测试获取最优解"""
        optimizer = NSGA2Optimizer(
            objectives=self.objectives,
            n_candidates=400,
            n_samples=5,
            random_seed=42
        )

        result_pop = optimizer.optimize(
            population_size=20,
            n_generations=10,
            verbose=False
        )

        weights = np.array([0.5, 0.3, 0.2])
        best_solution = optimizer.get_best_solution(result_pop, weights)

        self.assertIsNotNone(best_solution)
        self.assertIsInstance(best_solution, Individual)


if __name__ == '__main__':
    unittest.main()
