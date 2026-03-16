# 多目标优化采样系统

Multi-Objective Optimization Sampling System

## 概述

这是一个用于优化采样点选择的多目标优化系统，综合考虑方差、成本、可达性等多个目标，推荐最优采样点组合。

## 主要特性

- 支持多目标优化（NSGA-II算法）
- 可配置的目标函数和约束条件
- 帕累托前沿计算和可视化
- 高性能优化引擎
- 易于扩展的架构

## 安装

```bash
pip install numpy shapely
```

## 快速开始

### 基本使用

```python
import numpy as np
from multi_objective_optimization import NSGA2Optimizer, VarianceObjective, CostObjective, AccessibilityObjective

# 创建测试数据
variance_grid = np.random.rand(100, 100)
x_coords = np.arange(100)
y_coords = np.arange(100)

# 创建目标函数
objectives = [
    VarianceObjective(variance_grid, x_coords, y_coords, weight=0.5),
    CostObjective(base_location=(0, 0), weight=0.3),
    AccessibilityObjective(base_location=(0, 0), weight=0.2),
]

# 创建优化器
optimizer = NSGA2Optimizer(
    objectives=objectives,
    n_candidates=10000,
    n_samples=20,
    random_seed=42
)

# 运行优化
result = optimizer.optimize(
    population_size=100,
    n_generations=100,
    crossover_prob=0.9,
    mutation_prob=0.1,
    verbose=True
)

# 获取帕累托前沿
pareto_front = result.get_pareto_front()
print(f"帕累托前沿规模: {len(pareto_front)}")

# 获取推荐方案
weights = np.array([0.5, 0.3, 0.2])
best_solution = optimizer.get_best_solution(result, weights)
print(f"推荐方案目标值: {best_solution.objectives}")
```

### 添加约束条件

```python
from multi_objective_optimization import BoundaryConstraint, DistanceConstraint, BudgetConstraint

# 创建边界约束
boundary = [(0, 0), (100, 0), (100, 100), (0, 100)]
boundary_constraint = BoundaryConstraint(boundary, x_coords, y_coords)

# 创建距离约束
distance_constraint = DistanceConstraint(min_distance=10.0, x_coords=x_coords, y_coords=y_coords)

# 创建预算约束
budget_constraint = BudgetConstraint(budget=50000, base_location=(0, 0))

# 创建带约束的优化器
optimizer = NSGA2Optimizer(
    objectives=objectives,
    constraints=[boundary_constraint, distance_constraint, budget_constraint],
    n_candidates=10000,
    n_samples=20
)
```

### 自定义目标函数

```python
from multi_objective_optimization.objectives.base import BaseObjective

class CustomObjective(BaseObjective):
    def __init__(self, weight=1.0):
        super().__init__(name='custom', weight=weight, direction='minimize')

    def evaluate(self, individual):
        # 实现你的评估逻辑
        # 返回目标函数值
        return 0.0

# 使用自定义目标函数
objectives.append(CustomObjective(weight=0.1))
```

## 模块说明

### 核心模块 (core)

- `optimizer.py`: 优化器基类
- `nsga2.py`: NSGA-II算法实现
- `population.py`: 种群和个体类

### 目标函数模块 (objectives)

- `base.py`: 目标函数基类
- `variance.py`: 方差最小化目标
- `cost.py`: 成本最小化目标
- `accessibility.py`: 可达性最大化目标

### 约束条件模块 (constraints)

- `base.py`: 约束条件基类
- `boundary.py`: 边界约束
- `distance.py`: 距离约束
- `budget.py`: 预算约束

### 工具模块 (utils)

- `geometry.py`: 几何计算工具
- `metrics.py`: 性能指标计算

## 测试

运行单元测试：

```bash
python -m pytest multi_objective_optimization/tests/
```

或者使用unittest：

```bash
python -m unittest multi_objective_optimization.tests.test_core
```

## 性能优化

### 并行计算

```python
# 使用多进程加速
optimizer.optimize(
    population_size=100,
    n_generations=100,
    verbose=True
)
```

### 缓存机制

系统自动缓存重复计算结果以提高性能。

## 性能指标

系统提供多种性能指标：

- 超体积 (Hypervolume)
- 间距 (Spacing)
- 分布度 (Spread)
- 多样性 (Diversity)
- IGD (Inverted Generational Distance)

```python
from multi_objective_optimization.utils.metrics import calculate_performance_metrics

metrics = calculate_performance_metrics(result)
print(metrics)
```

## 参数调优建议

| 参数 | 推荐值 | 说明 |
|-----|--------|------|
| population_size | 50-200 | 种群规模 |
| n_generations | 50-200 | 进化代数 |
| crossover_prob | 0.7-0.9 | 交叉概率 |
| mutation_prob | 0.05-0.2 | 变异概率 |

## 文档

- [需求规格说明书](需求规格说明书.md)
- [算法设计文档](算法设计文档.md)
- [API接口设计文档](API接口设计文档.md)

## 许可证

MIT License

## 作者

iFlow CLI

## 版本

1.0.0