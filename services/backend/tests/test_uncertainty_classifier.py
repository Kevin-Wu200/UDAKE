"""
不确定性分级模型测试
"""
import pytest
import numpy as np
from pathlib import Path
import sys

# 添加模块路径
sys.path.append(str(Path(__file__).parent.parent.parent))
from uncertainty_dashboard.不确定性分级模型 import (
    UncertaintyClassifier,
    UncertaintyLevel
)


@pytest.fixture
def classifier():
    """创建不确定性分级器实例"""
    return UncertaintyClassifier()


@pytest.fixture
def sample_variance():
    """创建示例方差数据"""
    # 创建一个10x10的方差矩阵，范围0.01-0.99
    np.random.seed(42)
    return np.random.rand(10, 10) * 0.98 + 0.01


@pytest.fixture
def sample_variance_all_same():
    """创建所有值相同的方差数据"""
    return np.ones((5, 5)) * 0.5


@pytest.fixture
def sample_coordinates():
    """创建示例坐标数据"""
    x_coords = np.linspace(0, 9, 10)
    y_coords = np.linspace(0, 9, 10)
    return x_coords, y_coords


class TestUncertaintyClassifier:
    """测试不确定性分级器"""

    def test_initialization(self, classifier):
        """测试类初始化"""
        assert classifier is not None
        assert hasattr(classifier, 'thresholds')
        assert UncertaintyLevel.VERY_LOW in classifier.thresholds
        assert UncertaintyLevel.LOW in classifier.thresholds
        assert UncertaintyLevel.MEDIUM in classifier.thresholds
        assert UncertaintyLevel.HIGH in classifier.thresholds

    def test_classify_uncertainty(self, classifier, sample_variance):
        """测试不确定性分级"""
        result = classifier.classify_uncertainty(sample_variance)

        # 验证返回类型
        assert isinstance(result, np.ndarray)
        assert result.shape == sample_variance.shape

        # 验证分级范围 (0-4)
        assert np.all(result >= 0)
        assert np.all(result <= 4)

        # 验证返回的是整数
        assert result.dtype in [np.int32, np.int64]

    def test_classify_uncertainty_with_custom_thresholds(self, classifier, sample_variance):
        """测试使用自定义阈值"""
        custom_thresholds = {
            UncertaintyLevel.VERY_LOW: 0.3,
            UncertaintyLevel.LOW: 0.5,
            UncertaintyLevel.MEDIUM: 0.7,
            UncertaintyLevel.HIGH: 0.9
        }

        result1 = classifier.classify_uncertainty(sample_variance.copy())
        result2 = classifier.classify_uncertainty(sample_variance.copy(), custom_thresholds)

        # 验证阈值被更新
        assert classifier.thresholds[UncertaintyLevel.VERY_LOW] == 0.3

    def test_classify_uncertainty_uniform_data(self, classifier, sample_variance_all_same):
        """测试统一数据分级"""
        result = classifier.classify_uncertainty(sample_variance_all_same)

        # 验证所有点都被分类为相同的等级
        assert len(np.unique(result)) == 1
        # 归一化后应该都是0
        assert np.all(result == 0)

    def test_get_level_statistics(self, classifier, sample_variance):
        """测试获取等级统计信息"""
        stats = classifier.get_level_statistics(sample_variance)

        # 验证返回类型
        assert isinstance(stats, dict)

        # 验证包含所有等级
        expected_levels = ["very_low", "low", "medium", "high", "very_high"]
        for level in expected_levels:
            assert level in stats
            assert "count" in stats[level]
            assert "percentage" in stats[level]
            assert "level_code" in stats[level]

        # 验证数据类型
        for level in expected_levels:
            assert isinstance(stats[level]["count"], int)
            assert isinstance(stats[level]["percentage"], float)
            assert isinstance(stats[level]["level_code"], int)

        # 验证总和
        total_count = sum(stats[level]["count"] for level in expected_levels)
        assert total_count == sample_variance.size

        total_percentage = sum(stats[level]["percentage"] for level in expected_levels)
        assert abs(total_percentage - 100.0) < 1e-6

    def test_generate_uncertainty_map(self, classifier, sample_variance, sample_coordinates):
        """测试生成不确定性地图"""
        x_coords, y_coords = sample_coordinates
        result = classifier.generate_uncertainty_map(sample_variance, x_coords, y_coords)

        # 验证返回结构
        assert "classified_map" in result
        assert "statistics" in result
        assert "color_map" in result
        assert "x_coords" in result
        assert "y_coords" in result

        # 验证 classified_map
        assert result["classified_map"].shape == sample_variance.shape

        # 验证 color_map 包含所有等级的颜色
        assert len(result["color_map"]) == 5
        for i in range(5):
            assert i in result["color_map"]

        # 验证坐标
        assert isinstance(result["x_coords"], list)
        assert isinstance(result["y_coords"], list)
        assert len(result["x_coords"]) == len(x_coords)
        assert len(result["y_coords"]) == len(y_coords)

    def test_identify_critical_zones(self, classifier, sample_variance, sample_coordinates):
        """测试识别关键区域"""
        x_coords, y_coords = sample_coordinates
        critical_level = 3  # 高和很高

        critical_zones = classifier.identify_critical_zones(
            sample_variance, x_coords, y_coords, critical_level
        )

        # 验证返回类型
        assert isinstance(critical_zones, list)

        # 验证每个关键区域的格式
        if len(critical_zones) > 0:
            zone = critical_zones[0]
            assert "x" in zone
            assert "y" in zone
            assert "variance" in zone
            assert "level" in zone

            # 验证级别
            assert zone["level"] >= critical_level

    def test_identify_critical_zones_with_default_level(self, classifier, sample_variance, sample_coordinates):
        """测试使用默认的关键级别"""
        x_coords, y_coords = sample_coordinates
        critical_zones = classifier.identify_critical_zones(
            sample_variance, x_coords, y_coords
        )

        # 应该使用默认级别 3
        for zone in critical_zones:
            assert zone["level"] >= 3

    def test_identify_critical_zones_no_critical(self, classifier, sample_coordinates):
        """测试无关键区域的情况"""
        # 创建一个非常低的方差数据
        variance = np.ones((5, 5)) * 0.01
        x_coords, y_coords = sample_coordinates

        # 只使用前5个坐标
        critical_zones = classifier.identify_critical_zones(
            variance, x_coords[:5], y_coords[:5]
        )

        # 可能有或者没有关键区域，但应该返回列表
        assert isinstance(critical_zones, list)

    def test_normalize_method(self, classifier):
        """测试归一化方法（私有方法）"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        normalized = classifier._normalize(data)

        # 验证范围
        assert np.min(normalized) == 0.0
        assert np.max(normalized) == 1.0

        # 验证形状
        assert normalized.shape == data.shape

    def test_normalize_method_all_same(self, classifier):
        """测试相同数据的归一化"""
        data = np.ones((5, 5)) * 0.5
        normalized = classifier._normalize(data)

        # 验证全为0
        assert np.all(normalized == 0)

    def test_edge_case_empty_variance(self, classifier):
        """测试空方差数据"""
        with pytest.raises((ValueError, IndexError)):
            classifier.classify_uncertainty(np.array([]))

    def test_edge_case_single_value(self, classifier):
        """测试单一值"""
        variance = np.array([[0.5]])
        result = classifier.classify_uncertainty(variance)

        assert result.shape == variance.shape
        assert result[0, 0] == 0  # 归一化后应该为0

    def test_threshold_values(self, classifier):
        """测试阈值值的合理性"""
        # 验证阈值是递增的
        thresholds = [
            classifier.thresholds[UncertaintyLevel.VERY_LOW],
            classifier.thresholds[UncertaintyLevel.LOW],
            classifier.thresholds[UncertaintyLevel.MEDIUM],
            classifier.thresholds[UncertaintyLevel.HIGH]
        ]

        for i in range(len(thresholds) - 1):
            assert thresholds[i] < thresholds[i+1]

    def test_variance_with_negative_values(self, classifier):
        """测试包含负值的方差数据"""
        # 虽然方差不应该为负，但测试鲁棒性
        variance = np.array([[0.1, -0.1], [0.5, 0.8]])
        result = classifier.classify_uncertainty(variance)

        assert result.shape == variance.shape
        assert np.all(result >= 0)
        assert np.all(result <= 4)