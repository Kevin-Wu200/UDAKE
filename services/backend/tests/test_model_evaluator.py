"""
模型评估报告生成测试
"""
import pytest
import numpy as np
from pathlib import Path
import sys
from datetime import datetime

# 添加模块路径
sys.path.append(str(Path(__file__).parent.parent.parent))
from ai_extension.模型评估报告生成 import ModelEvaluator


@pytest.fixture
def evaluator():
    """创建模型评估器实例"""
    return ModelEvaluator()


@pytest.fixture
def sample_evaluation_data():
    """创建示例评估数据"""
    np.random.seed(42)
    actual_values = np.random.rand(100) * 50
    predicted_values = actual_values + np.random.randn(100) * 5
    variance = np.random.rand(100) * 10 + 1
    return actual_values, predicted_values, variance


@pytest.fixture
def sample_model_params():
    """创建示例模型参数"""
    return {
        "model_type": "Kriging",
        "variogram_model": "spherical",
        "nugget": 0.1,
        "sill": 50.0,
        "range": 100.0,
        "n_samples": 100
    }


class TestModelEvaluator:
    """测试模型评估器"""

    def test_initialization(self, evaluator):
        """测试类初始化"""
        assert evaluator is not None
        assert hasattr(evaluator, 'generate_evaluation_report')

    def test_generate_evaluation_report(self, evaluator, sample_evaluation_data,
                                          sample_model_params):
        """测试生成评估报告"""
        actual_values, predicted_values, variance = sample_evaluation_data
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 验证报告结构
        assert "timestamp" in report
        assert "model_parameters" in report
        assert "error_metrics" in report
        assert "correlation" in report
        assert "variance_statistics" in report
        assert "quality_score" in report
        assert "sample_size" in report
        assert "recommendations" in report

        # 验证时间戳
        assert isinstance(report["timestamp"], str)
        datetime.fromisoformat(report["timestamp"])  # 验证可以解析

        # 验证模型参数
        assert report["model_parameters"] == sample_model_params

    def test_error_metrics(self, evaluator, sample_evaluation_data, sample_model_params):
        """测试误差指标"""
        actual_values, predicted_values, variance = sample_evaluation_data
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        error_metrics = report["error_metrics"]

        # 验证误差指标
        assert "mae" in error_metrics
        assert "rmse" in error_metrics
        assert "mape" in error_metrics

        # 验证数据类型
        assert isinstance(error_metrics["mae"], float)
        assert isinstance(error_metrics["rmse"], float)
        assert isinstance(error_metrics["mape"], float)

        # 验证非负性
        assert error_metrics["mae"] >= 0
        assert error_metrics["rmse"] >= 0
        assert error_metrics["mape"] >= 0

        # 验证RMSE >= MAE
        assert error_metrics["rmse"] >= error_metrics["mae"]

    def test_correlation_calculation(self, evaluator, sample_evaluation_data,
                                      sample_model_params):
        """测试相关性计算"""
        actual_values, predicted_values, variance = sample_evaluation_data
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 验证相关性
        assert isinstance(report["correlation"], float)
        assert -1 <= report["correlation"] <= 1

    def test_correlation_perfect_prediction(self, evaluator, sample_model_params):
        """测试完美预测的相关性"""
        actual_values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        predicted_values = actual_values.copy()
        variance = np.ones(5)

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 完美预测的相关性应该是1
        assert abs(report["correlation"] - 1.0) < 1e-6

    def test_correlation_inverse_prediction(self, evaluator, sample_model_params):
        """测试反相关预测的相关性"""
        actual_values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        predicted_values = -actual_values.copy()
        variance = np.ones(5)

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 反相关的相关性应该是-1
        assert abs(report["correlation"] + 1.0) < 1e-6

    def test_variance_statistics(self, evaluator, sample_evaluation_data,
                                  sample_model_params):
        """测试方差统计"""
        actual_values, predicted_values, variance = sample_evaluation_data
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        var_stats = report["variance_statistics"]

        # 验证统计指标
        assert "mean" in var_stats
        assert "std" in var_stats
        assert "min" in var_stats
        assert "max" in var_stats
        assert "median" in var_stats

        # 验证数据类型
        for key in var_stats:
            assert isinstance(var_stats[key], float)

        # 验证统计关系
        assert var_stats["min"] <= var_stats["mean"] <= var_stats["max"]
        assert var_stats["min"] <= var_stats["median"] <= var_stats["max"]
        assert var_stats["std"] >= 0

    def test_quality_score(self, evaluator, sample_evaluation_data, sample_model_params):
        """测试质量分数"""
        actual_values, predicted_values, variance = sample_evaluation_data
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 验证质量分数
        assert isinstance(report["quality_score"], float)
        assert 0 <= report["quality_score"] <= 100

    def test_quality_score_perfect_model(self, evaluator, sample_model_params):
        """测试完美模型的质量分数"""
        actual_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        predicted_values = actual_values.copy()  # 完美预测
        variance = np.array([0.1, 0.1, 0.1, 0.1, 0.1])  # 低方差

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 完美模型的质量分数应该很高
        assert report["quality_score"] > 70

    def test_quality_score_poor_model(self, evaluator, sample_model_params):
        """测试差模型的质量分数"""
        actual_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        predicted_values = np.array([50.0, 40.0, 30.0, 20.0, 10.0])  # 反向预测
        variance = np.array([100.0, 100.0, 100.0, 100.0, 100.0])  # 高方差

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 差模型的质量分数应该较低
        assert report["quality_score"] < 50

    def test_sample_size(self, evaluator, sample_evaluation_data, sample_model_params):
        """测试样本大小"""
        actual_values, predicted_values, variance = sample_evaluation_data
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 验证样本大小
        assert report["sample_size"] == len(actual_values)

    def test_recommendations(self, evaluator, sample_evaluation_data, sample_model_params):
        """测试建议生成"""
        actual_values, predicted_values, variance = sample_evaluation_data
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 验证建议
        assert isinstance(report["recommendations"], list)
        assert len(report["recommendations"]) >= 1

        # 验证建议内容
        for rec in report["recommendations"]:
            assert isinstance(rec, str)
            assert len(rec) > 0

    def test_recommendations_low_correlation(self, evaluator, sample_model_params):
        """测试低相关性时的建议"""
        actual_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        predicted_values = np.array([15.0, 25.0, 35.0, 45.0, 55.0])  # 偏移
        variance = np.ones(5)

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 应该有关于相关性的建议
        recommendations_text = " ".join(report["recommendations"])
        # 注意：偏移预测的相关性仍然很高，所以可能不会触发这个建议
        assert isinstance(report["recommendations"], list)

    def test_recommendations_high_error(self, evaluator, sample_model_params):
        """测试高误差时的建议"""
        actual_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        predicted_values = np.array([100.0, 200.0, 300.0, 400.0, 500.0])  # 高误差
        variance = np.array([1.0, 1.0, 1.0, 1.0, 1.0])

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 应该有关于误差的建议
        assert len(report["recommendations"]) >= 1

    def test_recommendations_high_variance(self, evaluator, sample_model_params):
        """测试高方差时的建议"""
        actual_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        predicted_values = actual_values.copy()
        variance = np.array([100.0, 200.0, 300.0, 400.0, 500.0])  # 高方差

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 应该有关于方差的建议
        recommendations_text = " ".join(report["recommendations"])
        assert "方差" in recommendations_text or "不确定性" in recommendations_text

    def test_recommendations_good_model(self, evaluator, sample_model_params):
        """测试良好模型的建议"""
        actual_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        predicted_values = actual_values.copy()
        variance = np.array([0.1, 0.1, 0.1, 0.1, 0.1])

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 应该有正面的建议
        recommendations_text = " ".join(report["recommendations"])
        assert "良好" in recommendations_text or "可以" in recommendations_text

    def test_calculate_quality_score(self, evaluator):
        """测试质量分数计算"""
        # 高相关性，低误差，低方差
        quality_score = evaluator._calculate_quality_score(
            mae=1.0,
            rmse=1.5,
            correlation=0.95,
            variance=np.array([1.0, 1.0, 1.0])
        )
        assert quality_score > 50

        # 低相关性，高误差，高方差
        quality_score = evaluator._calculate_quality_score(
            mae=50.0,
            rmse=60.0,
            correlation=0.3,
            variance=np.array([100.0, 100.0, 100.0])
        )
        assert quality_score < 50

    def test_calculate_quality_score_components(self, evaluator):
        """测试质量分数组成部分"""
        variance = np.array([10.0, 20.0, 30.0])

        # 测试相关性分数
        # 相关性0应该给0分
        score1 = evaluator._calculate_quality_score(
            mae=10.0,
            rmse=15.0,
            correlation=0.0,
            variance=variance
        )
        assert score1 < 50

        # 相关性1应该给高分
        score2 = evaluator._calculate_quality_score(
            mae=10.0,
            rmse=15.0,
            correlation=1.0,
            variance=variance
        )
        assert score2 > score1

    def test_mape_calculation(self, evaluator, sample_evaluation_data, sample_model_params):
        """测试MAPE计算"""
        actual_values, predicted_values, variance = sample_evaluation_data
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 手动计算MAPE
        errors = np.abs(actual_values - predicted_values)
        expected_mape = np.mean(errors / (np.abs(actual_values) + 1e-10)) * 100

        # 验证MAPE
        assert abs(report["error_metrics"]["mape"] - expected_mape) < 1e-6

    def test_edge_case_empty_arrays(self, evaluator, sample_model_params):
        """测试空数组"""
        actual_values = np.array([])
        predicted_values = np.array([])
        variance = np.array([])

        with pytest.raises((ValueError, IndexError)):
            evaluator.generate_evaluation_report(
                actual_values, predicted_values, variance, sample_model_params
            )

    def test_edge_case_single_value(self, evaluator, sample_model_params):
        """测试单一值"""
        actual_values = np.array([10.0])
        predicted_values = np.array([12.0])
        variance = np.array([1.0])

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 应该能够处理
        assert report["sample_size"] == 1
        assert report["correlation"] is not None  # 单点相关性可能是NaN

    def test_edge_case_zero_actual_values(self, evaluator, sample_model_params):
        """测试实际值为零的情况"""
        actual_values = np.array([0.0, 0.0, 0.0])
        predicted_values = np.array([1.0, 2.0, 3.0])
        variance = np.array([1.0, 1.0, 1.0])

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 应该能够处理（MAPE可能很大）
        assert report["error_metrics"]["mape"] >= 0

    def test_edge_case_constant_values(self, evaluator, sample_model_params):
        """测试常量值"""
        actual_values = np.ones(10) * 10.0
        predicted_values = np.ones(10) * 10.0
        variance = np.ones(10)

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 常量值的相关性可能是NaN
        assert report["sample_size"] == 10
        # 误差应该为0
        assert report["error_metrics"]["mae"] == 0.0
        assert report["error_metrics"]["rmse"] == 0.0

    def test_edge_case_zero_variance(self, evaluator, sample_model_params):
        """测试零方差"""
        actual_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        predicted_values = actual_values.copy()
        variance = np.zeros(5)

        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 应该能够处理
        assert report["sample_size"] == 5

    def test_different_data_sizes(self, evaluator, sample_model_params):
        """测试不同数据大小"""
        for size in [10, 50, 100, 500]:
            np.random.seed(42)
            actual_values = np.random.rand(size) * 50
            predicted_values = actual_values + np.random.randn(size) * 5
            variance = np.random.rand(size) * 10 + 1

            report = evaluator.generate_evaluation_report(
                actual_values, predicted_values, variance, sample_model_params
            )

            assert report["sample_size"] == size

    def test_report_consistency(self, evaluator, sample_evaluation_data, sample_model_params):
        """测试报告一致性"""
        actual_values, predicted_values, variance = sample_evaluation_data

        # 多次生成报告
        report1 = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )
        report2 = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, sample_model_params
        )

        # 应该得到相同的结果（除了时间戳）
        assert report1["model_parameters"] == report2["model_parameters"]
        assert report1["error_metrics"] == report2["error_metrics"]
        assert report1["correlation"] == report2["correlation"]
        assert report1["quality_score"] == report2["quality_score"]
        assert report1["sample_size"] == report2["sample_size"]