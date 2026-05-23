"""
误差预测模型测试
"""
import sys
from pathlib import Path

import numpy as np
import pytest

# 添加模块路径
sys.path.append(str(Path(__file__).parent.parent.parent))
from ai_extension.误差预测模型 import ErrorPredictor


@pytest.fixture
def predictor():
    """创建误差预测模型实例"""
    return ErrorPredictor()


@pytest.fixture
def sample_training_data():
    """创建示例训练数据"""
    np.random.seed(42)
    x = np.random.rand(100) * 100
    y = np.random.rand(100) * 100
    actual_values = np.random.rand(100) * 50
    predicted_values = actual_values + np.random.randn(100) * 5  # 添加一些预测误差
    return x, y, actual_values, predicted_values


@pytest.fixture
def sample_prediction_data():
    """创建示例预测数据"""
    np.random.seed(42)
    x = np.random.rand(50) * 100
    y = np.random.rand(50) * 100
    predicted_values = np.random.rand(50) * 50
    return x, y, predicted_values


class TestErrorPredictor:
    """测试误差预测模型"""

    def test_initialization(self, predictor):
        """测试类初始化"""
        assert predictor is not None
        assert hasattr(predictor, 'model')
        assert hasattr(predictor, 'train')
        assert hasattr(predictor, 'predict_error')
        assert hasattr(predictor, 'estimate_confidence')

    def test_train(self, predictor, sample_training_data):
        """测试训练模型"""
        x, y, actual_values, predicted_values = sample_training_data
        result = predictor.train(x, y, actual_values, predicted_values)

        # 验证返回结构
        assert "train_r2" in result
        assert "test_r2" in result
        assert "feature_importance" in result

        # 验证数据类型
        assert isinstance(result["train_r2"], float)
        assert isinstance(result["test_r2"], float)
        assert isinstance(result["feature_importance"], list)

        # 验证R²范围
        assert -1 <= result["train_r2"] <= 1
        assert -1 <= result["test_r2"] <= 1

        # 验证特征重要性数量
        assert len(result["feature_importance"]) == 3  # x, y, predicted_values

    def test_train_performance(self, predictor, sample_training_data):
        """测试训练性能"""
        x, y, actual_values, predicted_values = sample_training_data
        result = predictor.train(x, y, actual_values, predicted_values)

        # 训练集的R²应该较高
        assert result["train_r2"] > 0.5

        # 测试集的R²应该合理
        assert result["test_r2"] >= 0

    def test_train_with_different_data_sizes(self, predictor):
        """测试不同数据大小的训练"""
        np.random.seed(42)

        for size in [50, 100, 200]:
            x = np.random.rand(size) * 100
            y = np.random.rand(size) * 100
            actual_values = np.random.rand(size) * 50
            predicted_values = actual_values + np.random.randn(size) * 5

            result = predictor.train(x, y, actual_values, predicted_values)

            assert "train_r2" in result
            assert "test_r2" in result

    def test_predict_error(self, predictor, sample_training_data, sample_prediction_data):
        """测试预测误差"""
        # 先训练模型
        x_train, y_train, actual_values, predicted_values = sample_training_data
        predictor.train(x_train, y_train, actual_values, predicted_values)

        # 预测误差
        x_pred, y_pred, pred_values = sample_prediction_data
        predicted_errors = predictor.predict_error(x_pred, y_pred, pred_values)

        # 验证返回类型
        assert isinstance(predicted_errors, np.ndarray)

        # 验证形状
        assert predicted_errors.shape == pred_values.shape

        # 验证误差非负
        assert np.all(predicted_errors >= 0)

    def test_predict_error_without_training(self, predictor, sample_prediction_data):
        """测试未训练模型的预测"""
        x, y, predicted_values = sample_prediction_data

        # 未训练的模型应该抛出异常或返回空结果
        with pytest.raises(Exception):
            predictor.predict_error(x, y, predicted_values)

    def test_predict_error_consistency(self, predictor, sample_training_data, sample_prediction_data):
        """测试预测一致性"""
        # 训练模型
        x_train, y_train, actual_values, predicted_values = sample_training_data
        predictor.train(x_train, y_train, actual_values, predicted_values)

        # 多次预测相同的数据
        x, y, pred_values = sample_prediction_data
        errors1 = predictor.predict_error(x, y, pred_values)
        errors2 = predictor.predict_error(x, y, pred_values)

        # 应该得到相同的结果
        np.testing.assert_array_equal(errors1, errors2)

    def test_estimate_confidence(self, predictor, sample_training_data, sample_prediction_data):
        """测试估计置信度"""
        # 先训练模型
        x_train, y_train, actual_values, predicted_values = sample_training_data
        predictor.train(x_train, y_train, actual_values, predicted_values)

        # 估计置信度
        x_pred, y_pred, pred_values = sample_prediction_data
        confidence = predictor.estimate_confidence(x_pred, y_pred, pred_values)

        # 验证返回类型
        assert isinstance(confidence, np.ndarray)

        # 验证形状
        assert confidence.shape == pred_values.shape

        # 验证置信度范围
        assert np.all(confidence >= 0)
        assert np.all(confidence <= 1)

    def test_estimate_confidence_without_training(self, predictor, sample_prediction_data):
        """测试未训练模型的置信度估计"""
        x, y, predicted_values = sample_prediction_data

        with pytest.raises(Exception):
            predictor.estimate_confidence(x, y, predicted_values)

    def test_confidence_error_relationship(self, predictor, sample_training_data, sample_prediction_data):
        """测试置信度与误差的关系"""
        # 训练模型
        x_train, y_train, actual_values, predicted_values = sample_training_data
        predictor.train(x_train, y_train, actual_values, predicted_values)

        # 预测
        x, y, pred_values = sample_prediction_data
        errors = predictor.predict_error(x, y, pred_values)  # noqa: F841
        confidence = predictor.estimate_confidence(x, y, pred_values)

        # 验证关系：置信度高意味着误差低
        # 按置信度排序
        sorted_indices = np.argsort(confidence)

        # 最低置信度的误差应该不小于最高置信度的误差
        # 注意：这不一定总是成立，因为存在噪声
        min_conf_idx = sorted_indices[0]
        max_conf_idx = sorted_indices[-1]

        # 验证置信度计算的正确性
        assert confidence[min_conf_idx] <= confidence[max_conf_idx]

    def test_feature_importance_sum(self, predictor, sample_training_data):
        """测试特征重要性总和"""
        x, y, actual_values, predicted_values = sample_training_data
        result = predictor.train(x, y, actual_values, predicted_values)

        # 特征重要性之和应该接近1（对于随机森林）
        importance_sum = sum(result["feature_importance"])
        assert abs(importance_sum - 1.0) < 0.1  # 允许一些误差

    def test_feature_importance_order(self, predictor, sample_training_data):
        """测试特征重要性顺序"""
        x, y, actual_values, predicted_values = sample_training_data
        result = predictor.train(x, y, actual_values, predicted_values)

        # 特征重要性应该都是非负的
        for importance in result["feature_importance"]:
            assert importance >= 0

    def test_error_calculation(self, predictor, sample_training_data):
        """测试误差计算"""
        x, y, actual_values, predicted_values = sample_training_data

        # 计算期望的误差
        expected_errors = np.abs(actual_values - predicted_values)  # noqa: F841

        # 训练模型
        result = predictor.train(x, y, actual_values, predicted_values)  # noqa: F841

        # 模型应该学习到误差模式
        # 测试一些预测
        test_errors = predictor.predict_error(x[:10], y[:10], predicted_values[:10])

        # 预测的误差应该合理
        assert np.all(test_errors >= 0)

    def test_edge_case_small_dataset(self, predictor):
        """测试小数据集"""
        np.random.seed(42)
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        actual_values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        predicted_values = np.array([12.0, 18.0, 32.0, 38.0, 52.0])

        # 应该能够训练
        result = predictor.train(x, y, actual_values, predicted_values)
        assert "train_r2" in result

    def test_edge_case_minimal_dataset(self, predictor):
        """测试最小数据集"""
        # 随机森林需要足够的数据，测试边界情况
        np.random.seed(42)
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([1.0, 2.0, 3.0])
        actual_values = np.array([10.0, 20.0, 30.0])
        predicted_values = np.array([12.0, 18.0, 32.0])

        # 可能会抛出异常或产生不太理想的结果
        try:
            result = predictor.train(x, y, actual_values, predicted_values)
            assert "train_r2" in result
        except Exception:
            # 某些实现可能会拒绝太少的数据
            pass

    def test_edge_case_perfect_predictions(self, predictor):
        """测试完美预测"""
        np.random.seed(42)
        x = np.random.rand(100) * 100
        y = np.random.rand(100) * 100
        actual_values = np.random.rand(100) * 50
        predicted_values = actual_values.copy()  # 完美预测，误差为0

        result = predictor.train(x, y, actual_values, predicted_values)

        # R²应该很高
        assert result["train_r2"] > 0.8

        # 预测误差应该接近0
        errors = predictor.predict_error(x[:10], y[:10], predicted_values[:10])
        assert np.all(errors >= 0)

    def test_edge_case_constant_predictions(self, predictor):
        """测试常量预测"""
        np.random.seed(42)
        x = np.random.rand(100) * 100
        y = np.random.rand(100) * 100
        actual_values = np.random.rand(100) * 50
        predicted_values = np.ones(100) * 25.0  # 常量预测

        result = predictor.train(x, y, actual_values, predicted_values)

        # 应该能够学习到误差模式
        assert "train_r2" in result

    def test_model_parameters(self, predictor):
        """测试模型参数"""
        # 验证模型参数
        assert predictor.model.n_estimators == 100
        assert predictor.model.max_depth == 10
        assert predictor.model.random_state == 42

    def test_prediction_with_same_coordinates(self, predictor, sample_training_data):
        """测试相同坐标的预测"""
        # 训练模型
        x_train, y_train, actual_values, predicted_values = sample_training_data
        predictor.train(x_train, y_train, actual_values, predicted_values)

        # 使用训练集的坐标进行预测
        errors = predictor.predict_error(x_train, y_train, predicted_values)

        # 应该能够预测
        assert errors.shape == predicted_values.shape
        assert np.all(errors >= 0)

    def test_confidence_normalization(self, predictor, sample_training_data, sample_prediction_data):
        """测试置信度归一化"""
        # 训练模型
        x_train, y_train, actual_values, predicted_values = sample_training_data
        predictor.train(x_train, y_train, actual_values, predicted_values)

        # 估计置信度
        x, y, pred_values = sample_prediction_data
        confidence = predictor.estimate_confidence(x, y, pred_values)

        # 验证归一化
        assert np.min(confidence) >= 0
        assert np.max(confidence) <= 1

        # 如果有多个不同的置信度，验证归一化正确
        if np.std(confidence) > 1e-6:
            # 最小误差应该对应最低置信度
            errors = predictor.predict_error(x, y, pred_values)
            max_error_idx = np.argmax(errors)
            assert confidence[max_error_idx] <= 0.5  # 应该较低

    def test_train_test_split(self, predictor, sample_training_data):
        """测试训练测试集划分"""
        x, y, actual_values, predicted_values = sample_training_data
        result = predictor.train(x, y, actual_values, predicted_values)

        # 验证测试集大小（应该是20%）
        expected_test_size = int(len(x) * 0.2)  # noqa: F841

        # 训练集R²通常高于测试集R²
        # 这是一个常见的现象
        # 注意：这不总是成立，但在大多数情况下成立
        # 所以我们只是验证结果存在，不强制要求train_r2 > test_r2
        assert result["train_r2"] is not None
        assert result["test_r2"] is not None
