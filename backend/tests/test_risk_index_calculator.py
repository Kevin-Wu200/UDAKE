"""
风险指数计算测试
"""
import pytest
import numpy as np
from pathlib import Path
import sys

# 添加模块路径
sys.path.append(str(Path(__file__).parent.parent.parent))
from uncertainty_dashboard.风险指数计算 import RiskIndexCalculator


@pytest.fixture
def calculator():
    """创建风险指数计算器实例"""
    return RiskIndexCalculator()


@pytest.fixture
def sample_variance():
    """创建示例方差数据"""
    np.random.seed(42)
    return np.random.rand(10, 10) * 0.5 + 0.01


@pytest.fixture
def sample_prediction():
    """创建示例预测数据"""
    np.random.seed(42)
    return np.random.rand(10, 10) * 100


@pytest.fixture
def sample_coordinates():
    """创建示例坐标数据"""
    x_coords = np.linspace(0, 9, 10)
    y_coords = np.linspace(0, 9, 10)
    return x_coords, y_coords


@pytest.fixture
def historical_data():
    """创建历史数据用于时间趋势分析"""
    np.random.seed(42)
    variances = [np.random.rand(5, 5) * 0.5 for _ in range(5)]
    predictions = [np.random.rand(5, 5) * 100 for _ in range(5)]
    return variances, predictions


class TestRiskIndexCalculator:
    """测试风险指数计算器"""

    def test_initialization(self, calculator):
        """测试类初始化"""
        assert calculator is not None
        assert hasattr(calculator, 'calculate_risk_index')
        assert hasattr(calculator, 'calculate_spatial_risk')
        assert hasattr(calculator, 'calculate_temporal_risk_trend')

    def test_calculate_risk_index(self, calculator, sample_variance, sample_prediction):
        """测试计算风险指数"""
        risk_index = calculator.calculate_risk_index(sample_variance, sample_prediction)

        # 验证返回类型
        assert isinstance(risk_index, np.ndarray)

        # 验证形状
        assert risk_index.shape == sample_variance.shape

        # 验证范围 [0, 1]
        assert np.all(risk_index >= 0.0)
        assert np.all(risk_index <= 1.0)

    def test_calculate_risk_index_with_all_same_data(self, calculator):
        """测试相同数据的风险指数"""
        variance = np.ones((5, 5)) * 0.5
        prediction = np.ones((5, 5)) * 50.0

        risk_index = calculator.calculate_risk_index(variance, prediction)

        # 归一化后应该是0
        assert np.all(risk_index == 0)

    def test_calculate_risk_index_shape_consistency(self, calculator):
        """测试不同形状的数据"""
        shapes = [(5, 5), (3, 4), (10, 10)]

        for shape in shapes:
            variance = np.random.rand(*shape) * 0.5
            prediction = np.random.rand(*shape) * 100

            risk_index = calculator.calculate_risk_index(variance, prediction)

            assert risk_index.shape == shape

    def test_calculate_spatial_risk(self, calculator, sample_variance, sample_prediction):
        """测试计算空间风险"""
        x_coords, y_coords = sample_coordinates
        result = calculator.calculate_spatial_risk(
            sample_variance, sample_prediction, x_coords, y_coords
        )

        # 验证返回结构
        assert "risk_index" in result
        assert "statistics" in result
        assert "risk_levels" in result
        assert "high_risk_area" in result
        assert "high_risk_percentage" in result

        # 验证 risk_index
        assert result["risk_index"].shape == sample_variance.shape

        # 验证统计信息
        stats = result["statistics"]
        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats
        assert "median" in stats

        # 验证数据类型
        assert isinstance(stats["mean"], float)
        assert isinstance(stats["std"], float)

        # 验证风险等级
        risk_levels = result["risk_levels"]
        assert "low" in risk_levels
        assert "medium" in risk_levels
        assert "high" in risk_levels

        # 验证高风险区域
        assert isinstance(result["high_risk_area"], int)
        assert isinstance(result["high_risk_percentage"], float)

        # 验证高风险区域范围
        assert 0 <= result["high_risk_percentage"] <= 100

    def test_calculate_spatial_risk_statistics_validity(self, calculator, sample_variance, sample_prediction):
        """测试空间风险统计的有效性"""
        x_coords, y_coords = sample_coordinates
        result = calculator.calculate_spatial_risk(
            sample_variance, sample_prediction, x_coords, y_coords
        )

        stats = result["statistics"]

        # 验证统计关系
        assert stats["min"] <= stats["mean"] <= stats["max"]
        assert stats["min"] <= stats["median"] <= stats["max"]
        assert stats["std"] >= 0

    def test_calculate_spatial_risk_levels_sum(self, calculator, sample_variance, sample_prediction):
        """测试风险等级总和"""
        x_coords, y_coords = sample_coordinates
        result = calculator.calculate_spatial_risk(
            sample_variance, sample_prediction, x_coords, y_coords
        )

        risk_levels = result["risk_levels"]
        total = risk_levels["low"] + risk_levels["medium"] + risk_levels["high"]

        assert total == sample_variance.size

    def test_calculate_temporal_risk_trend(self, calculator, historical_data):
        """测试时间风险趋势"""
        variances, predictions = historical_data
        result = calculator.calculate_temporal_risk_trend(variances, predictions)

        # 验证返回结构
        assert "risk_trends" in result
        assert "trend_direction" in result
        assert "change_rate" in result

        # 验证趋势列表
        assert len(result["risk_trends"]) == len(variances)

        # 验证趋势方向
        assert result["trend_direction"] in ["上升", "下降", "稳定"]

        # 验证变化率
        assert isinstance(result["change_rate"], float)

    def test_calculate_temporal_risk_trend_single_point(self, calculator):
        """测试单点时间趋势"""
        variance = [np.random.rand(5, 5) * 0.5]
        prediction = [np.random.rand(5, 5) * 100]

        result = calculator.calculate_temporal_risk_trend(variance, prediction)

        # 验证趋势为稳定
        assert result["trend_direction"] == "稳定"
        assert result["change_rate"] == 0.0

    def test_calculate_temporal_risk_trend_length_consistency(self, calculator):
        """测试时间趋势长度一致性"""
        variances = [np.random.rand(3, 3) * 0.5 for _ in range(3)]
        predictions = [np.random.rand(3, 3) * 100 for _ in range(3)]

        result = calculator.calculate_temporal_risk_trend(variances, predictions)

        assert len(result["risk_trends"]) == 3

    def test_normalize_method(self, calculator):
        """测试归一化方法"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        normalized = calculator._normalize(data)

        # 验证范围
        assert np.min(normalized) == 0.0
        assert np.max(normalized) == 1.0

    def test_normalize_method_all_same(self, calculator):
        """测试相同数据的归一化"""
        data = np.ones((5, 5)) * 0.5
        normalized = calculator._normalize(data)

        # 验证全为0
        assert np.all(normalized == 0)

    def test_classify_risk_levels(self, calculator):
        """测试风险等级分类"""
        risk_index = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])

        levels = calculator._classify_risk_levels(risk_index)

        # 验证返回结构
        assert "low" in levels
        assert "medium" in levels
        assert "high" in levels

        # 验证总和
        total = levels["low"] + levels["medium"] + levels["high"]
        assert total == len(risk_index)

    def test_classify_risk_levels_all_low(self, calculator):
        """测试全低风险"""
        risk_index = np.array([0.1, 0.2, 0.3])

        levels = calculator._classify_risk_levels(risk_index)

        assert levels["low"] == 3
        assert levels["medium"] == 0
        assert levels["high"] == 0

    def test_classify_risk_levels_all_high(self, calculator):
        """测试全高风险"""
        risk_index = np.array([0.7, 0.8, 0.9])

        levels = calculator._classify_risk_levels(risk_index)

        assert levels["low"] == 0
        assert levels["medium"] == 0
        assert levels["high"] == 3

    def test_edge_case_empty_arrays(self, calculator):
        """测试空数组"""
        variance = np.array([])
        prediction = np.array([])

        with pytest.raises((ValueError, IndexError)):
            calculator.calculate_risk_index(variance, prediction)

    def test_edge_case_single_value(self, calculator):
        """测试单一值"""
        variance = np.array([[0.5]])
        prediction = np.array([[50.0]])

        risk_index = calculator.calculate_risk_index(variance, prediction)

        assert risk_index.shape == (1, 1)
        # 归一化后应该为0
        assert risk_index[0, 0] == 0.0

    def test_risk_index_weights(self, calculator):
        """测试风险指数权重"""
        # 创建测试数据：方差高，预测值低
        variance = np.array([[0.9]])
        prediction = np.array([[0.1]])

        risk_index = calculator.calculate_risk_index(variance, prediction)

        # 方差权重0.7，预测值权重0.3
        # 归一化后都是0，所以风险指数应该是0
        assert risk_index[0, 0] == 0.0

    def test_negative_prediction_values(self, calculator):
        """测试负预测值"""
        variance = np.array([[0.1, 0.2], [0.3, 0.4]])
        prediction = np.array([[-10.0, -20.0], [-30.0, -40.0]])

        risk_index = calculator.calculate_risk_index(variance, prediction)

        # 应该正常工作，使用绝对值
        assert risk_index.shape == variance.shape
        assert np.all(risk_index >= 0)
        assert np.all(risk_index <= 1)

    def test_high_risk_percentage_calculation(self, calculator, sample_variance, sample_prediction):
        """测试高风险百分比计算"""
        x_coords, y_coords = sample_coordinates
        result = calculator.calculate_spatial_risk(
            sample_variance, sample_prediction, x_coords, y_coords
        )

        # 验证高风险百分比与高风险区域的关系
        expected_percentage = result["high_risk_area"] / sample_variance.size * 100
        assert abs(result["high_risk_percentage"] - expected_percentage) < 1e-6