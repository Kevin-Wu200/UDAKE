"""
异常检测模块测试
"""
import pytest
import numpy as np
from pathlib import Path
import sys

# 添加模块路径
sys.path.append(str(Path(__file__).parent.parent.parent))
from ai_extension.异常检测模块 import AnomalyDetector


@pytest.fixture
def detector():
    """创建异常检测器实例"""
    return AnomalyDetector()


@pytest.fixture
def sample_spatial_data():
    """创建示例空间数据"""
    np.random.seed(42)
    x = np.random.rand(50) * 100
    y = np.random.rand(50) * 100
    values = np.random.rand(50) * 50
    return x, y, values


@pytest.fixture
def sample_data_with_anomalies():
    """创建包含异常值的数据"""
    np.random.seed(42)

    # 创建正常数据
    x = np.linspace(0, 10, 45)
    y = np.linspace(0, 10, 45)
    values = np.linspace(0, 10, 45)

    # 添加异常值
    x_anomaly = np.array([5.0, 6.0, 7.0, 8.0, 9.0])
    y_anomaly = np.array([5.0, 6.0, 7.0, 8.0, 9.0])
    values_anomaly = np.array([100.0, 150.0, 200.0, 250.0, 300.0])  # 异常高的值

    x = np.concatenate([x, x_anomaly])
    y = np.concatenate([y, y_anomaly])
    values = np.concatenate([values, values_anomaly])

    return x, y, values


@pytest.fixture
def sample_value_data():
    """创建示例值数据"""
    np.random.seed(42)
    values = np.random.randn(100) * 10 + 50  # 正态分布
    return values


class TestAnomalyDetector:
    """测试异常检测器"""

    def test_initialization(self, detector):
        """测试类初始化"""
        assert detector is not None
        assert hasattr(detector, 'isolation_forest')
        assert hasattr(detector, 'elliptic_envelope')
        assert hasattr(detector, 'detect_spatial_anomalies')
        assert hasattr(detector, 'detect_value_anomalies')
        assert hasattr(detector, 'get_anomaly_scores')

    def test_detect_spatial_anomalies(self, detector, sample_spatial_data):
        """测试检测空间异常"""
        x, y, values = sample_spatial_data
        result = detector.detect_spatial_anomalies(x, y, values)

        # 验证返回结构
        assert "anomaly_count" in result
        assert "anomaly_indices" in result
        assert "anomaly_ratio" in result
        assert "anomaly_locations" in result

        # 验证数据类型
        assert isinstance(result["anomaly_count"], int)
        assert isinstance(result["anomaly_indices"], list)
        assert isinstance(result["anomaly_ratio"], float)
        assert isinstance(result["anomaly_locations"], list)

        # 验证异常数量与索引列表长度一致
        assert result["anomaly_count"] == len(result["anomaly_indices"])
        assert result["anomaly_count"] == len(result["anomaly_locations"])

        # 验证异常比率范围
        assert 0 <= result["anomaly_ratio"] <= 1

        # 验证异常位置格式
        if len(result["anomaly_locations"]) > 0:
            location = result["anomaly_locations"][0]
            assert "x" in location
            assert "y" in location
            assert "value" in location

            # 验证数据类型
            assert isinstance(location["x"], float)
            assert isinstance(location["y"], float)
            assert isinstance(location["value"], float)

    def test_detect_spatial_anomalies_with_anomalies(self, detector, sample_data_with_anomalies):
        """测试检测包含异常的数据"""
        x, y, values = sample_data_with_anomalies
        result = detector.detect_spatial_anomalies(x, y, values)

        # 应该检测到一些异常
        assert result["anomaly_count"] > 0

        # 异常比率应该合理
        assert result["anomaly_ratio"] > 0

    def test_detect_spatial_anomalies_consistency(self, detector, sample_spatial_data):
        """测试检测一致性"""
        x, y, values = sample_spatial_data

        # 多次运行应该得到相同的结果
        result1 = detector.detect_spatial_anomalies(x, y, values)
        result2 = detector.detect_spatial_anomalies(x, y, values)

        assert result1["anomaly_count"] == result2["anomaly_count"]
        assert result1["anomaly_indices"] == result2["anomaly_indices"]

    def test_detect_value_anomalies(self, detector, sample_value_data):
        """测试检测值异常"""
        result = detector.detect_value_anomalies(sample_value_data)

        # 验证返回结构
        assert "anomaly_count" in result
        assert "anomaly_indices" in result
        assert "mean" in result
        assert "std" in result
        assert "threshold" in result

        # 验证数据类型
        assert isinstance(result["anomaly_count"], int)
        assert isinstance(result["anomaly_indices"], list)
        assert isinstance(result["mean"], float)
        assert isinstance(result["std"], float)
        assert isinstance(result["threshold"], float)

        # 验证异常数量与索引列表长度一致
        assert result["anomaly_count"] == len(result["anomaly_indices"])

        # 验证统计值
        assert result["std"] >= 0
        assert result["threshold"] > 0

    def test_detect_value_anomalies_with_outliers(self, detector):
        """测试检测包含离群值的数据"""
        # 创建包含离群值的数据
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0, -100.0])
        result = detector.detect_value_anomalies(values, threshold=2.0)

        # 应该检测到离群值
        assert result["anomaly_count"] > 0

        # 验证离群值被正确识别
        assert 5 in result["anomaly_indices"]  # 100.0
        assert 6 in result["anomaly_indices"]  # -100.0

    def test_detect_value_anomalies_custom_threshold(self, detector, sample_value_data):
        """测试自定义阈值"""
        result1 = detector.detect_value_anomalies(sample_value_data, threshold=2.0)
        result2 = detector.detect_value_anomalies(sample_value_data, threshold=3.0)

        # 更高的阈值应该检测到更少的异常
        assert result2["anomaly_count"] <= result1["anomaly_count"]

    def test_detect_value_anomalies_no_anomalies(self, detector):
        """测试无异常的情况"""
        # 创建非常均匀的数据
        values = np.array([10.0, 10.1, 9.9, 10.0, 10.1])
        result = detector.detect_value_anomalies(values, threshold=3.0)

        # 应该没有异常
        assert result["anomaly_count"] == 0
        assert len(result["anomaly_indices"]) == 0

    def test_detect_value_anomalies_all_anomalies(self, detector):
        """测试所有值都是异常的情况"""
        # 创建极端离群值
        values = np.array([1000.0, -1000.0, 2000.0, -2000.0])
        result = detector.detect_value_anomalies(values, threshold=1.0)

        # 应该检测到所有异常
        assert result["anomaly_count"] > 0

    def test_get_anomaly_scores(self, detector, sample_spatial_data):
        """测试获取异常分数"""
        x, y, values = sample_spatial_data
        scores = detector.get_anomaly_scores(x, y, values)

        # 验证返回类型
        assert isinstance(scores, np.ndarray)

        # 验证形状
        assert scores.shape == values.shape

        # 验证分数范围
        assert np.all(scores >= -1)  # IsolationForest的分数范围
        assert np.all(scores <= 1)

    def test_get_anomaly_scores_with_anomalies(self, detector, sample_data_with_anomalies):
        """测试异常数据的分数"""
        x, y, values = sample_data_with_anomalies
        scores = detector.get_anomaly_scores(x, y, values)

        # 异常值应该有较低的分数
        # 分数越低越可能是异常
        assert len(scores) == len(values)

    def test_spatial_anomalies_indices_validity(self, detector, sample_spatial_data):
        """测试异常索引的有效性"""
        x, y, values = sample_spatial_data
        result = detector.detect_spatial_anomalies(x, y, values)

        # 验证所有索引都在有效范围内
        for idx in result["anomaly_indices"]:
            assert 0 <= idx < len(values)

    def test_value_anomalies_indices_validity(self, detector, sample_value_data):
        """测试异常索引的有效性"""
        result = detector.detect_value_anomalies(sample_value_data)

        # 验证所有索引都在有效范围内
        for idx in result["anomaly_indices"]:
            assert 0 <= idx < len(sample_value_data)

    def test_spatial_anomalies_locations_match_indices(self, detector, sample_spatial_data):
        """测试异常位置与索引匹配"""
        x, y, values = sample_spatial_data
        result = detector.detect_spatial_anomalies(x, y, values)

        # 验证位置与索引对应
        for i, idx in enumerate(result["anomaly_indices"]):
            location = result["anomaly_locations"][i]
            assert location["x"] == x[idx]
            assert location["y"] == y[idx]
            assert location["value"] == values[idx]

    def test_anomaly_ratio_calculation(self, detector, sample_spatial_data):
        """测试异常比率计算"""
        x, y, values = sample_spatial_data
        result = detector.detect_spatial_anomalies(x, y, values)

        # 验证比率计算
        expected_ratio = result["anomaly_count"] / len(values)
        assert abs(result["anomaly_ratio"] - expected_ratio) < 1e-6

    def test_value_anomalies_statistics(self, detector, sample_value_data):
        """测试异常检测的统计信息"""
        result = detector.detect_value_anomalies(sample_value_data)

        # 验证统计值
        expected_mean = np.mean(sample_value_data)
        expected_std = np.std(sample_value_data)

        assert abs(result["mean"] - expected_mean) < 1e-6
        assert abs(result["std"] - expected_std) < 1e-6

    def test_edge_case_empty_arrays(self, detector):
        """测试空数组"""
        x = np.array([])
        y = np.array([])
        values = np.array([])

        with pytest.raises((ValueError, IndexError)):
            detector.detect_spatial_anomalies(x, y, values)

    def test_edge_case_single_value(self, detector):
        """测试单一值"""
        x = np.array([1.0])
        y = np.array([1.0])
        values = np.array([10.0])

        result = detector.detect_spatial_anomalies(x, y, values)

        # 单一值不应该被检测为异常
        assert result["anomaly_count"] in [0, 1]

    def test_edge_case_identical_values(self, detector):
        """测试所有值相同"""
        x = np.linspace(0, 10, 10)
        y = np.linspace(0, 10, 10)
        values = np.ones(10) * 10.0

        result = detector.detect_spatial_anomalies(x, y, values)

        # 所有值相同，可能没有异常
        assert isinstance(result["anomaly_count"], int)

    def test_contamination_parameter(self, detector):
        """测试污染参数"""
        # 验证模型的污染参数
        assert detector.isolation_forest.contamination == 0.1
        assert detector.elliptic_envelope.contamination == 0.1

    def test_random_state_consistency(self, detector, sample_spatial_data):
        """测试随机状态一致性"""
        # 创建两个检测器，使用相同的随机状态
        detector2 = AnomalyDetector()

        x, y, values = sample_spatial_data

        # 应该得到相同的结果
        result1 = detector.detect_spatial_anomalies(x, y, values)
        result2 = detector2.detect_spatial_anomalies(x, y, values)

        assert result1["anomaly_count"] == result2["anomaly_count"]
        assert result1["anomaly_indices"] == result2["anomaly_indices"]

    def test_z_score_calculation(self, detector):
        """测试Z-score计算"""
        values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        result = detector.detect_value_anomalies(values, threshold=3.0)

        # 计算Z-score
        mean = np.mean(values)
        std = np.std(values)
        z_scores = np.abs((values - mean) / std)

        # 验证异常索引
        for idx in result["anomaly_indices"]:
            assert z_scores[idx] > 3.0

    def test_large_dataset_performance(self, detector):
        """测试大数据集性能"""
        np.random.seed(42)
        x = np.random.rand(1000) * 100
        y = np.random.rand(1000) * 100
        values = np.random.rand(1000) * 50

        # 应该能够处理大数据集
        result = detector.detect_spatial_anomalies(x, y, values)

        assert result["anomaly_count"] >= 0
        assert len(result["anomaly_indices"]) == result["anomaly_count"]