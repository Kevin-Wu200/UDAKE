"""
准确性验证测试
Accuracy Validation Tests
"""

from datetime import datetime

import numpy as np
import pytest

from ..api.realtime_service import RealtimeService
from ..core.incremental_kriging import IncrementalKriging
from ..models import BoundingBox, DataPoint, Subscription


class TestIncrementalAccuracy:
    """增量算法准确性测试"""

    @pytest.fixture
    def kriging(self):
        """创建增量克里金实例"""
        return IncrementalKriging()

    def test_incremental_vs_full_prediction_accuracy(self, kriging):
        """测试增量预测与全量预测的准确性对比"""
        # 创建测试数据
        initial_data = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(20)
        ]

        # 全量计算
        kriging.initial_fit(initial_data)
        full_predictions = kriging.predict([(5.0, 5.0), (10.0, 10.0)])  # noqa: F841

        # 增量更新
        new_data = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(20, 30)
        ]
        kriging.incremental_update(new_data)
        incremental_predictions = kriging.predict([(5.0, 5.0), (10.0, 10.0)])

        # 重新计算全量结果
        kriging2 = IncrementalKriging()
        all_data = initial_data + new_data
        kriging2.initial_fit(all_data)
        full_after_update_predictions = kriging2.predict([(5.0, 5.0), (10.0, 10.0)])

        # 比较增量预测和全量预测
        for i in range(len(incremental_predictions)):
            increment_value = incremental_predictions[i].value
            full_value = full_after_update_predictions[i].value

            # 相对误差应该小于1%
            relative_error = abs(increment_value - full_value) / full_value
            assert relative_error < 0.01

            print(f"点 {i}:")
            print(f"  增量预测: {increment_value:.6f}")
            print(f"  全量预测: {full_value:.6f}")
            print(f"  相对误差: {relative_error * 100:.4f}%")

    def test_prediction_variance_validity(self, kriging):
        """测试预测方差的合理性"""
        # 创建规则分布的数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]

        kriging.initial_fit(data_points)

        # 在不同位置进行预测
        test_points = [
            (5.0, 5.0),  # 数据点附近
            (15.0, 15.0),  # 远离数据点
            (5.0, 15.0),  # 非对称位置
        ]

        predictions = kriging.predict(test_points)

        # 验证方差特性
        for pred in predictions:
            # 方差应该是非负的
            assert pred.variance >= 0

            # 方差不应该过大
            assert pred.variance < 1000

        # 数据点附近的方差应该较小
        assert predictions[0].variance < predictions[1].variance

        print("预测方差:")
        for i, pred in enumerate(predictions):
            print(f"  点 {test_points[i]}: {pred.variance:.6f}")

    def test_interpolation_error_bound(self, kriging):
        """测试插值误差边界"""
        # 创建已知函数的数据（使用简单的线性函数）
        def true_function(x, y):
            return 10.0 + 0.5 * x + 0.3 * y

        # 采样数据
        sample_data = [
            DataPoint(id=str(i), x=i, y=i, value=true_function(i, i), timestamp=datetime.now())
            for i in range(0, 20, 2)
        ]

        kriging.initial_fit(sample_data)

        # 在采样点之间进行预测
        test_points = [(1.0, 1.0), (3.0, 3.0), (5.0, 5.0)]
        predictions = kriging.predict(test_points)

        # 计算预测误差
        for i, point in enumerate(test_points):
            true_value = true_function(point[0], point[1])
            predicted_value = predictions[i].value
            error = abs(predicted_value - true_value)

            # 对于简单线性函数，误差应该很小
            assert error < 1.0

            print(f"点 {point}:")
            print(f"  真实值: {true_value:.6f}")
            print(f"  预测值: {predicted_value:.6f}")
            print(f"  误差: {error:.6f}")

    def test_cross_validation_accuracy(self, kriging):
        """测试交叉验证准确性"""
        # 创建数据集
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i + np.random.normal(0, 0.1), timestamp=datetime.now())
            for i in range(20)
        ]

        # 留一交叉验证
        errors = []
        for i in range(len(data_points)):
            # 留出一个点
            train_data = [dp for j, dp in enumerate(data_points) if j != i]
            test_point = data_points[i]

            # 训练模型
            kriging.initial_fit(train_data)

            # 预测留出的点
            predictions = kriging.predict([(test_point.x, test_point.y)])
            predicted_value = predictions[0].value

            # 计算误差
            error = abs(predicted_value - test_point.value)
            errors.append(error)

        # 计算平均误差
        mean_error = np.mean(errors)
        std_error = np.std(errors)

        print("交叉验证结果:")
        print(f"  平均误差: {mean_error:.6f}")
        print(f"  标准差: {std_error:.6f}")
        print(f"  最大误差: {max(errors):.6f}")

        # 平均误差应该合理
        assert mean_error < 2.0


class TestRealtimeServiceAccuracy:
    """实时服务准确性测试"""

    @pytest.fixture
    def realtime_service(self):
        """创建实时服务实例"""
        return RealtimeService()

    def test_service_prediction_consistency(self, realtime_service):
        """测试服务预测的一致性"""
        subscription = Subscription(
            id='consistency_test',
            name='一致性测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 添加数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]
        realtime_service.add_data_points(subscription.id, data_points)

        # 多次查询相同位置
        test_point = (5.0, 5.0)
        predictions = []

        for _ in range(5):
            pred = realtime_service.query_predictions(subscription.id, [test_point])
            predictions.append(pred[0].value)

        # 所有预测应该相同（或非常接近）
        mean_prediction = np.mean(predictions)
        std_prediction = np.std(predictions)

        print("多次预测结果:")
        for i, pred in enumerate(predictions):
            print(f"  第{i+1}次: {pred:.6f}")
        print(f"  平均值: {mean_prediction:.6f}")
        print(f"  标准差: {std_prediction:.8f}")

        # 标准差应该非常小（< 0.001）
        assert std_prediction < 0.001

    def test_batch_update_accuracy(self, realtime_service):
        """测试批量更新的准确性"""
        subscription = Subscription(
            id='batch_accuracy_test',
            name='批量更新准确性测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 初始数据
        initial_data = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(5)
        ]
        realtime_service.add_data_points(subscription.id, initial_data)

        # 获取初始预测
        initial_pred = realtime_service.query_predictions(subscription.id, [(2.5, 2.5)])

        # 批量添加数据
        batch_data = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(5, 15)
        ]
        realtime_service.add_data_points(subscription.id, batch_data)

        # 获取更新后的预测
        updated_pred = realtime_service.query_predictions(subscription.id, [(2.5, 2.5)])

        # 验证预测值发生了变化
        assert initial_pred[0].value != updated_pred[0].value

        print("批量更新前后预测:")
        print(f"  更新前: {initial_pred[0].value:.6f}")
        print(f"  更新后: {updated_pred[0].value:.6f}")

    def test_spatial_accuracy_gradient(self, realtime_service):
        """测试空间准确性的梯度"""
        subscription = Subscription(
            id='gradient_test',
            name='梯度测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 创建有明确梯度的数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]
        realtime_service.add_data_points(subscription.id, data_points)

        # 沿着梯度方向进行预测
        gradient_points = [(i, i) for i in range(1, 9)]
        predictions = realtime_service.query_predictions(subscription.id, gradient_points)

        # 验证预测值沿梯度方向递增
        for i in range(1, len(predictions)):
            assert predictions[i].value > predictions[i-1].value

        print("梯度预测结果:")
        for i, pred in enumerate(predictions):
            print(f"  点 {gradient_points[i]}: {pred.value:.6f}")

    def test_boundary_condition_accuracy(self, realtime_service):
        """测试边界条件的准确性"""
        subscription = Subscription(
            id='boundary_test',
            name='边界测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 在边界上放置数据点
        boundary_data = [
            DataPoint(id='0', x=0.0, y=0.0, value=10.0, timestamp=datetime.now()),
            DataPoint(id='1', x=10.0, y=0.0, value=20.0, timestamp=datetime.now()),
            DataPoint(id='2', x=0.0, y=10.0, value=15.0, timestamp=datetime.now()),
            DataPoint(id='3', x=10.0, y=10.0, value=25.0, timestamp=datetime.now()),
        ]
        realtime_service.add_data_points(subscription.id, boundary_data)

        # 在边界附近进行预测
        test_points = [
            (0.0, 0.0),  # 角点
            (10.0, 10.0),  # 对角
            (0.1, 0.1),  # 近角点
            (9.9, 9.9),  # 近对角
        ]

        predictions = realtime_service.query_predictions(subscription.id, test_points)

        # 验证边界预测的合理性
        for pred in predictions:
            # 预测值应该在数据点的范围内
            assert 10.0 <= pred.value <= 25.0

        print("边界预测结果:")
        for i, point in enumerate(test_points):
            print(f"  点 {point}: {predictions[i].value:.6f}")


class TestNumericalStability:
    """数值稳定性测试"""

    @pytest.fixture
    def kriging(self):
        """创建增量克里金实例"""
        return IncrementalKriging()

    def test_large_value_stability(self, kriging):
        """测试大值的数值稳定性"""
        # 使用较大的值
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=1e6 + i * 1e5, timestamp=datetime.now())
            for i in range(10)
        ]

        kriging.initial_fit(data_points)

        # 预测
        predictions = kriging.predict([(5.0, 5.0)])

        # 预测值应该是合理的
        assert not np.isnan(predictions[0].value)
        assert not np.isinf(predictions[0].value)
        assert predictions[0].value > 0

        print(f"大值预测: {predictions[0].value:.6f}")

    def test_small_value_stability(self, kriging):
        """测试小值的数值稳定性"""
        # 使用较小的值
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=1e-6 + i * 1e-7, timestamp=datetime.now())
            for i in range(10)
        ]

        kriging.initial_fit(data_points)

        # 预测
        predictions = kriging.predict([(5.0, 5.0)])

        # 预测值应该是合理的
        assert not np.isnan(predictions[0].value)
        assert not np.isinf(predictions[0].value)
        assert predictions[0].value > 0

        print(f"小值预测: {predictions[0].value:.10f}")

    def test_near_singular_matrix_stability(self, kriging):
        """测试接近奇异矩阵的稳定性"""
        # 创建几乎共线的数据点
        data_points = [
            DataPoint(id=str(i), x=i, y=i + 1e-10 * i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]

        kriging.initial_fit(data_points)

        # 预测
        predictions = kriging.predict([(5.0, 5.0)])

        # 应该能够处理接近奇异的情况
        assert not np.isnan(predictions[0].value)
        assert not np.isinf(predictions[0].value)

        print(f"接近奇异矩阵预测: {predictions[0].value:.6f}")

    def test_repeated_updates_stability(self, kriging):
        """测试重复更新的稳定性"""
        # 初始数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]

        kriging.initial_fit(data_points)

        # 重复添加相似的数据
        for iteration in range(10):
            new_data = [
                DataPoint(id=f'{iteration}_{i}', x=i, y=i, value=10.0 + i + iteration * 0.1, timestamp=datetime.now())
                for i in range(10, 12)
            ]
            kriging.incremental_update(new_data)

        # 最终预测
        predictions = kriging.predict([(5.0, 5.0)])

        # 应该保持稳定
        assert not np.isnan(predictions[0].value)
        assert not np.isinf(predictions[0].value)

        print(f"重复更新后预测: {predictions[0].value:.6f}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
