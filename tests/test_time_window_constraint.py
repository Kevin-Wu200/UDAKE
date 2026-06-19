"""
测试时间窗约束 (1099)
测试多目标优化模块中的 TimeWindowConstraint 类
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np

from multi_objective_optimization import TimeWindowConstraint
from multi_objective_optimization.core.population import Individual


def test_time_window_basic():
    """测试时间窗约束基本功能"""
    twc = TimeWindowConstraint(
        time_windows=[(0, 120), (30, 180), (60, 240)],
        max_total_time=480.0,
        time_per_sample=15.0,
        travel_speed=30.0,
        base_location=(0, 0),
        start_time=0.0,
    )
    assert twc.name == 'time_window'
    assert twc.max_total_time == 480.0
    assert twc.time_per_sample == 15.0
    assert twc.travel_speed == 30.0
    print("✓ 时间窗约束基本功能正常")


def test_time_window_satisfied():
    """测试个体满足时间窗约束"""
    twc = TimeWindowConstraint(
        time_windows=[(0, 120), (30, 180)],
        max_total_time=480.0,
        time_per_sample=10.0,
        travel_speed=60.0,
        base_location=(0, 0),
        start_time=0.0,
    )

    # 创建接近基地的个体（旅行时间短，应在时间窗内）
    ind = Individual(genes=[1, 2])
    ind.metadata = {'points': [(0.5, 0.5), (1.0, 1.0)]}

    violation = twc.evaluate(ind)
    assert violation >= 0, f"违反值应 >= 0，实际为 {violation}"

    # 检查是否满足约束
    satisfied = twc.is_satisfied(ind)
    print(f"✓ 时间窗约束评估正常，违反值: {violation:.2f}, 满足: {satisfied}")


def test_time_window_violation():
    """测试个体违反时间窗约束"""
    twc = TimeWindowConstraint(
        time_windows=[(0, 5), (0, 5)],  # 极短的时间窗
        max_total_time=10.0,  # 极短的总时间
        time_per_sample=5.0,
        travel_speed=1.0,  # 极慢的移动速度
        base_location=(0, 0),
        start_time=0.0,
    )

    # 创建远处的个体
    ind = Individual(genes=[1, 2])
    ind.metadata = {'points': [(100, 100), (200, 200)]}

    violation = twc.evaluate(ind)
    assert violation > 0, f"远距离个体应违反时间窗，实际违反值: {violation}"
    satisfied = twc.is_satisfied(ind)
    assert not satisfied, "远距离个体不应满足时间窗约束"
    print(f"✓ 时间窗违反检测正常，违反值: {violation:.2f}")


def test_get_total_time():
    """测试计算总时间"""
    twc = TimeWindowConstraint(
        max_total_time=480.0,
        time_per_sample=10.0,
        travel_speed=60.0,
        base_location=(0, 0),
        start_time=0.0,
    )

    ind = Individual(genes=[1, 2, 3])
    ind.metadata = {'points': [(1, 1), (2, 2), (3, 3)]}

    total_time = twc.get_total_time(ind)
    assert total_time > 0, f"总时间应 > 0，实际为 {total_time}"
    print(f"✓ 总时间计算正常: {total_time:.2f} 分钟")


def test_get_time_window_violations():
    """测试获取时间窗违反详情"""
    twc = TimeWindowConstraint(
        time_windows=[(0, 10), (100, 200)],
        max_total_time=480.0,
        time_per_sample=5.0,
        travel_speed=60.0,
        base_location=(0, 0),
        start_time=0.0,
    )

    ind = Individual(genes=[1, 2])
    ind.metadata = {'points': [(1, 1), (2, 2)]}

    violations = twc.get_time_window_violations(ind)
    assert len(violations) == 2
    assert 'arrival_time' in violations[0]
    assert 'in_window' in violations[0]
    print(f"✓ 时间窗违反详情获取正常，共 {len(violations)} 个采样点")


def test_empty_individual():
    """测试空个体（无采样点）"""
    twc = TimeWindowConstraint(
        max_total_time=480.0,
        time_per_sample=15.0,
        travel_speed=30.0,
    )

    ind = Individual(genes=[])
    violation = twc.evaluate(ind)
    assert violation == 0.0, f"空个体违反值应为0，实际为 {violation}"
    assert twc.is_satisfied(ind), "空个体应满足约束"
    print("✓ 空个体处理正常")


def test_index_based_coordinates():
    """测试基于索引的坐标映射"""
    x_coords = np.array([0.0, 1.0, 2.0, 3.0])
    y_coords = np.array([0.0, 1.0, 2.0])

    twc = TimeWindowConstraint(
        max_total_time=480.0,
        time_per_sample=5.0,
        travel_speed=30.0,
        x_coords=x_coords,
        y_coords=y_coords,
    )

    ind = Individual(genes=[0, 5])
    violation = twc.evaluate(ind)
    assert violation >= 0
    print(f"✓ 基于索引的坐标映射正常，违反值: {violation:.2f}")


def test_metadata_total_time_reuse():
    """测试 metadata 中 total_time 的缓存复用"""
    twc = TimeWindowConstraint(
        max_total_time=480.0,
        time_per_sample=10.0,
        travel_speed=60.0,
    )

    ind = Individual(genes=[1, 2])
    ind.metadata = {'points': [(1, 1), (2, 2)]}

    # 首次调用计算
    t1 = twc.get_total_time(ind)
    # 二次调用应从缓存读取
    t2 = twc.get_total_time(ind)
    assert t1 == t2, "缓存应返回相同值"
    print(f"✓ 总时间缓存复用正常: {t1:.2f}")


if __name__ == '__main__':
    test_time_window_basic()
    test_time_window_satisfied()
    test_time_window_violation()
    test_get_total_time()
    test_get_time_window_violations()
    test_empty_individual()
    test_index_based_coordinates()
    test_metadata_total_time_reuse()
    print("\n🎉 所有时间窗约束测试通过!")
