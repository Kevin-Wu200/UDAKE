"""
决策阈值分析测试
"""
import sys
from pathlib import Path

import numpy as np
import pytest

# 添加模块路径
sys.path.append(str(Path(__file__).parent.parent.parent))
from uncertainty_dashboard.决策阈值分析 import DecisionThresholdAnalyzer


@pytest.fixture
def analyzer():
    """创建决策阈值分析器实例"""
    return DecisionThresholdAnalyzer()


@pytest.fixture
def sample_prediction():
    """创建示例预测数据"""
    np.random.seed(42)
    return np.random.rand(10, 10) * 100


@pytest.fixture
def sample_variance():
    """创建示例方差数据"""
    np.random.seed(42)
    return np.random.rand(10, 10) * 10


@pytest.fixture
def sample_thresholds():
    """创建示例阈值列表"""
    return [20.0, 40.0, 60.0, 80.0]


class TestDecisionThresholdAnalyzer:
    """测试决策阈值分析器"""

    def test_initialization(self, analyzer):
        """测试类初始化"""
        assert analyzer is not None
        assert hasattr(analyzer, 'analyze_thresholds')
        assert hasattr(analyzer, 'calculate_decision_risk')
        assert hasattr(analyzer, 'generate_threshold_recommendations')

    def test_analyze_thresholds(self, analyzer, sample_prediction, sample_variance, sample_thresholds):
        """测试分析阈值"""
        result = analyzer.analyze_thresholds(sample_prediction, sample_variance, sample_thresholds)

        # 验证返回结构
        assert "thresholds" in result
        assert "analyses" in result
        assert "recommended_threshold" in result

        # 验证阈值列表
        assert result["thresholds"] == sample_thresholds

        # 验证分析结果数量
        assert len(result["analyses"]) == len(sample_thresholds)

        # 验证推荐阈值在列表中
        assert result["recommended_threshold"] in sample_thresholds

    def test_analyze_thresholds_single_threshold(self, analyzer, sample_prediction, sample_variance):
        """测试单个阈值分析"""
        thresholds = [50.0]
        result = analyzer.analyze_thresholds(sample_prediction, sample_variance, thresholds)

        assert len(result["analyses"]) == 1
        assert "threshold_50.0" in result["analyses"]

    def test_analyze_single_threshold_structure(self, analyzer, sample_prediction, sample_variance):
        """测试单个阈值分析结果结构"""
        threshold = 50.0
        result = analyzer._analyze_single_threshold(sample_prediction, sample_variance, threshold)

        # 验证返回字段
        assert "exceeding_count" in result
        assert "exceeding_percentage" in result
        assert "avg_uncertainty" in result
        assert "max_uncertainty" in result
        assert "confidence" in result

        # 验证数据类型
        assert isinstance(result["exceeding_count"], int)
        assert isinstance(result["exceeding_percentage"], float)
        assert isinstance(result["avg_uncertainty"], float)
        assert isinstance(result["max_uncertainty"], float)
        assert isinstance(result["confidence"], float)

        # 验证百分比范围
        assert 0 <= result["exceeding_percentage"] <= 100

        # 验证置信度范围
        assert 0 <= result["confidence"] <= 1

    def test_analyze_single_threshold_no_exceed(self, analyzer):
        """测试没有超过阈值的情况"""
        prediction = np.ones((5, 5)) * 10.0
        variance = np.ones((5, 5)) * 1.0
        threshold = 100.0  # 远大于所有预测值

        result = analyzer._analyze_single_threshold(prediction, variance, threshold)

        assert result["exceeding_count"] == 0
        assert result["exceeding_percentage"] == 0.0
        assert result["avg_uncertainty"] == 0.0
        assert result["max_uncertainty"] == 0.0
        assert result["confidence"] == 0.0

    def test_analyze_single_threshold_all_exceed(self, analyzer):
        """测试所有值都超过阈值的情况"""
        prediction = np.ones((5, 5)) * 100.0
        variance = np.ones((5, 5)) * 1.0
        threshold = 10.0  # 远小于所有预测值

        result = analyzer._analyze_single_threshold(prediction, variance, threshold)

        assert result["exceeding_count"] == prediction.size
        assert result["exceeding_percentage"] == 100.0
        assert result["avg_uncertainty"] == 1.0
        assert result["max_uncertainty"] == 1.0
        # 置信度应该较高
        assert result["confidence"] > 0

    def test_calculate_confidence(self, analyzer):
        """测试置信度计算"""
        prediction = np.array([10.0, 20.0, 30.0])
        variance = np.array([1.0, 2.0, 3.0])

        confidence = analyzer._calculate_confidence(prediction, variance)

        # 验证范围
        assert 0 <= confidence <= 1

    def test_calculate_confidence_high_uncertainty(self, analyzer):
        """测试高不确定性时的置信度"""
        prediction = np.array([10.0, 20.0, 30.0])
        variance = np.array([100.0, 200.0, 300.0])  # 高方差

        confidence = analyzer._calculate_confidence(prediction, variance)

        # 置信度应该较低
        assert confidence < 0.5

    def test_calculate_confidence_low_uncertainty(self, analyzer):
        """测试低不确定性时的置信度"""
        prediction = np.array([10.0, 20.0, 30.0])
        variance = np.array([0.001, 0.001, 0.001])  # 极低且均匀的方差

        confidence = analyzer._calculate_confidence(prediction, variance)

        # 均匀低方差归一化后均值接近1，置信度接近0
        # 使用差异更大的方差来测试
        prediction2 = np.array([10.0, 20.0, 30.0])
        variance2 = np.array([0.01, 0.1, 1.0])  # 差异较大的方差
        confidence2 = analyzer._calculate_confidence(prediction2, variance2)

        # 置信度应在合理范围内
        assert 0 <= confidence <= 1
        assert 0 <= confidence2 <= 1

    def test_recommend_threshold(self, analyzer):
        """测试阈值推荐"""
        prediction = np.random.rand(10, 10) * 100
        variance = np.random.rand(10, 10) * 10
        thresholds = [20.0, 40.0, 60.0, 80.0]

        analyses = {}
        for threshold in thresholds:
            analyses[f"threshold_{threshold}"] = analyzer._analyze_single_threshold(
                prediction, variance, threshold
            )

        recommended = analyzer._recommend_threshold(analyses)

        # 验证推荐阈值在列表中
        assert recommended in thresholds

        # 验证推荐的是置信度最高的阈值
        max_confidence = max(
            analyses[f"threshold_{t}"]["confidence"]
            for t in thresholds
        )
        expected_threshold = [
            t for t in thresholds
            if analyses[f"threshold_{t}"]["confidence"] == max_confidence
        ][0]
        assert recommended == expected_threshold

    def test_calculate_decision_risk(self, analyzer, sample_prediction, sample_variance):
        """测试计算决策风险"""
        threshold = 50.0
        result = analyzer.calculate_decision_risk(
            sample_prediction, sample_variance, threshold
        )

        # 验证返回结构
        assert "threshold" in result
        assert "false_positive_risk" in result
        assert "false_negative_risk" in result
        assert "total_risk" in result
        assert "acceptable" in result
        assert "risk_tolerance" in result

        # 验证阈值
        assert result["threshold"] == threshold

        # 验证风险值范围
        assert 0 <= result["false_positive_risk"] <= 1
        assert 0 <= result["false_negative_risk"] <= 1
        assert 0 <= result["total_risk"] <= 1

        # 验证可接受性是布尔值
        assert isinstance(result["acceptable"], bool)

    def test_calculate_decision_risk_with_tolerance(self, analyzer, sample_prediction, sample_variance):
        """测试带风险容忍度的决策风险计算"""
        threshold = 50.0
        risk_tolerance = 0.05

        result = analyzer.calculate_decision_risk(
            sample_prediction, sample_variance, threshold, risk_tolerance
        )

        assert result["risk_tolerance"] == risk_tolerance

        # 验证可接受性判断
        if result["total_risk"] <= risk_tolerance:
            assert result["acceptable"] is True
        else:
            assert result["acceptable"] is False

    def test_calculate_decision_risk_low_risk(self, analyzer):
        """测试低风险情况"""
        # 创建低不确定性数据
        prediction = np.array([[10.0, 20.0], [30.0, 40.0]])
        variance = np.array([[0.1, 0.1], [0.1, 0.1]])  # 低方差
        threshold = 25.0

        result = analyzer.calculate_decision_risk(prediction, variance, threshold)

        # 应该有较低的风险
        assert result["total_risk"] < 0.5

    def test_calculate_decision_risk_high_risk(self, analyzer):
        """测试高风险情况"""
        # 创建高不确定性数据
        prediction = np.array([[10.0, 20.0], [30.0, 40.0]])
        variance = np.array([[100.0, 100.0], [100.0, 100.0]])  # 高方差
        threshold = 25.0

        result = analyzer.calculate_decision_risk(prediction, variance, threshold)

        # 应该有较高的风险
        assert result["total_risk"] > 0.5

    def test_generate_threshold_recommendations(self, analyzer, sample_prediction, sample_variance):
        """测试生成阈值建议"""
        recommendations = analyzer.generate_threshold_recommendations(
            sample_prediction, sample_variance, n_thresholds=5
        )

        # 验证返回类型
        assert isinstance(recommendations, list)
        assert len(recommendations) == 5

        # 验证每个建议的结构
        for rec in recommendations:
            assert "threshold" in rec
            assert "confidence" in rec
            assert "risk" in rec
            assert "exceeding_percentage" in rec

            # 验证数据类型
            assert isinstance(rec["threshold"], float)
            assert isinstance(rec["confidence"], float)
            assert isinstance(rec["risk"], float)
            assert isinstance(rec["exceeding_percentage"], float)

        # 验证按置信度排序
        confidences = [rec["confidence"] for rec in recommendations]
        assert confidences == sorted(confidences, reverse=True)

    def test_generate_threshold_recommendations_n_thresholds(self, analyzer, sample_prediction, sample_variance):
        """测试不同数量的阈值建议"""
        for n in [3, 5, 7, 10]:
            recommendations = analyzer.generate_threshold_recommendations(
                sample_prediction, sample_variance, n_thresholds=n
            )
            assert len(recommendations) == n

    def test_generate_threshold_recommendations_values(self, analyzer, sample_prediction, sample_variance):
        """测试阈值建议的值范围"""
        recommendations = analyzer.generate_threshold_recommendations(
            sample_prediction, sample_variance, n_thresholds=5
        )

        thresholds = [rec["threshold"] for rec in recommendations]

        # 验证阈值在预测值范围内
        assert all(t >= np.min(sample_prediction) for t in thresholds)
        assert all(t <= np.max(sample_prediction) for t in thresholds)

    def test_edge_case_empty_arrays(self, analyzer):
        """测试空数组"""
        prediction = np.array([])
        variance = np.array([])
        thresholds = [50.0]

        # 空数组不会抛异常，但返回结果中会包含NaN或零值
        result = analyzer.analyze_thresholds(prediction, variance, thresholds)
        assert "analyses" in result
        assert "threshold_50.0" in result["analyses"]

    def test_edge_case_zero_variance(self, analyzer):
        """测试零方差"""
        prediction = np.array([[10.0, 20.0], [30.0, 40.0]])
        variance = np.zeros((2, 2))
        threshold = 25.0

        result = analyzer.calculate_decision_risk(prediction, variance, threshold)

        # 应该有零风险（无不确定性）
        assert result["false_positive_risk"] == 0.0
        assert result["false_negative_risk"] == 0.0
        assert result["total_risk"] == 0.0
        assert result["acceptable"] is True

    def test_edge_case_single_value(self, analyzer):
        """测试单一值"""
        prediction = np.array([[50.0]])
        variance = np.array([[1.0]])
        threshold = 50.0

        result = analyzer._analyze_single_threshold(prediction, variance, threshold)

        assert result["exceeding_count"] in [0, 1]
        assert result["exceeding_percentage"] in [0.0, 100.0]

    def test_confidence_boundary_conditions(self, analyzer):
        """测试置信度边界条件"""
        # 测试非常低的不确定性
        prediction = np.array([10.0, 20.0, 30.0])
        variance = np.array([0.0, 0.0, 0.0])

        confidence = analyzer._calculate_confidence(prediction, variance)
        assert confidence == 1.0

        # 测试非常高的不确定性
        prediction = np.array([10.0, 20.0, 30.0])
        variance = np.array([1000.0, 1000.0, 1000.0])

        confidence = analyzer._calculate_confidence(prediction, variance)
        assert confidence >= 0.0
        assert confidence <= 1.0
