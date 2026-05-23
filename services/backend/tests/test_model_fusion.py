"""
模型融合系统测试
"""
import pytest
from app.model_fusion.core.fusion_engine import FusionEngine
from app.model_fusion.core.fusion_models import (
    FusionConfig,
    FusionStrategy,
    ModelPrediction,
    WeightConfig,
    WeightMethod,
)
from app.model_fusion.core.weight_calculator import WeightCalculator
from app.model_fusion.evaluation.model_evaluator import ModelEvaluator


class TestWeightCalculator:
    """权重计算器测试"""

    @pytest.fixture
    def calculator(self):
        return WeightCalculator()

    @pytest.fixture
    def sample_metrics(self):
        from app.model_fusion.core.fusion_models import ModelMetrics
        return [
            ModelMetrics(
                model_id="model1",
                model_name="Model 1",
                rmse=1.2,
                mae=0.8,
                r2=0.85,
                stability=0.9
            ),
            ModelMetrics(
                model_id="model2",
                model_name="Model 2",
                rmse=1.5,
                mae=1.0,
                r2=0.80,
                stability=0.85
            ),
            ModelMetrics(
                model_id="model3",
                model_name="Model 3",
                rmse=1.0,
                mae=0.7,
                r2=0.90,
                stability=0.95
            )
        ]

    def test_equal_weights(self, calculator, sample_metrics):
        """测试等权重计算"""
        weights = calculator.calculate_weights(
            WeightMethod.EQUAL,
            sample_metrics
        )

        assert len(weights) == 3
        for weight in weights.values():
            assert abs(weight - 1/3) < 1e-6

    def test_rmse_based_weights(self, calculator, sample_metrics):
        """测试基于RMSE的权重计算"""
        weights = calculator.calculate_weights(
            WeightMethod.RMSE_BASED,
            sample_metrics
        )

        assert len(weights) == 3
        assert sum(weights.values()) == pytest.approx(1.0)
        # RMSE最小的模型应该有最大的权重
        assert weights['model3'] > weights['model1'] > weights['model2']

    def test_r2_based_weights(self, calculator, sample_metrics):
        """测试基于R²的权重计算"""
        weights = calculator.calculate_weights(
            WeightMethod.R2_BASED,
            sample_metrics
        )

        assert len(weights) == 3
        assert sum(weights.values()) == pytest.approx(1.0)
        # R²最大的模型应该有最大的权重
        assert weights['model3'] > weights['model1'] > weights['model2']

    def test_weight_constraints(self, calculator, sample_metrics):
        """测试权重约束"""
        weights = calculator.calculate_weights(
            WeightMethod.RMSE_BASED,
            sample_metrics,
            min_weight=0.1,
            max_weight=0.8
        )

        for weight in weights.values():
            assert 0.1 <= weight <= 0.8

    def test_weight_normalization(self, calculator, sample_metrics):
        """测试权重归一化"""
        weights = calculator.calculate_weights(
            WeightMethod.RMSE_BASED,
            sample_metrics,
            normalize=True
        )

        assert sum(weights.values()) == pytest.approx(1.0)


class TestModelEvaluator:
    """模型评估器测试"""

    @pytest.fixture
    def evaluator(self):
        return ModelEvaluator()

    @pytest.fixture
    def sample_predictions(self):
        return [
            ModelPrediction(
                model_id="model1",
                model_name="Model 1",
                predictions=[10.5, 11.2, 10.8, 11.5, 10.9]
            ),
            ModelPrediction(
                model_id="model2",
                model_name="Model 2",
                predictions=[10.8, 11.0, 10.9, 11.3, 11.1]
            )
        ]

    @pytest.fixture
    def sample_true_values(self):
        return [10.6, 11.0, 10.9, 11.2, 10.8]

    def test_evaluate_models(self, evaluator, sample_predictions, sample_true_values):
        """测试模型评估"""
        metrics = evaluator.evaluate_models(sample_predictions, sample_true_values)

        assert len(metrics) == 2
        assert all(m.rmse >= 0 for m in metrics)
        assert all(m.mae >= 0 for m in metrics)
        assert all(0 <= m.r2 <= 1 for m in metrics)

    def test_evaluate_fusion_result(self, evaluator, sample_true_values):
        """测试融合结果评估"""
        fusion_predictions = [10.65, 11.1, 10.85, 11.4, 11.0]
        metrics = evaluator.evaluate_fusion_result(fusion_predictions, sample_true_values)

        assert 'rmse' in metrics
        assert 'mae' in metrics
        assert 'r2' in metrics
        assert metrics['rmse'] >= 0
        assert metrics['mae'] >= 0
        assert 0 <= metrics['r2'] <= 1

    def test_calculate_rmse(self, evaluator):
        """测试RMSE计算"""
        predictions = [1.0, 2.0, 3.0, 4.0, 5.0]
        true_values = [1.1, 2.1, 2.9, 4.1, 4.9]

        rmse = evaluator._calculate_rmse(predictions, true_values)
        assert rmse >= 0
        assert abs(rmse - 0.1) < 0.01

    def test_calculate_mae(self, evaluator):
        """测试MAE计算"""
        predictions = [1.0, 2.0, 3.0, 4.0, 5.0]
        true_values = [1.1, 2.1, 2.9, 4.1, 4.9]

        mae = evaluator._calculate_mae(predictions, true_values)
        assert mae >= 0
        assert abs(mae - 0.1) < 0.01

    def test_calculate_r2(self, evaluator):
        """测试R²计算"""
        predictions = [1.0, 2.0, 3.0, 4.0, 5.0]
        true_values = [1.0, 2.0, 3.0, 4.0, 5.0]

        r2 = evaluator._calculate_r2(predictions, true_values)
        assert abs(r2 - 1.0) < 1e-6


class TestFusionEngine:
    """融合引擎测试"""

    @pytest.fixture
    def engine(self):
        return FusionEngine()

    @pytest.fixture
    def sample_models(self):
        return [
            ModelPrediction(
                model_id="model1",
                model_name="Model 1",
                predictions=[10.5, 11.2, 10.8, 11.5, 10.9]
            ),
            ModelPrediction(
                model_id="model2",
                model_name="Model 2",
                predictions=[10.8, 11.0, 10.9, 11.3, 11.1]
            ),
            ModelPrediction(
                model_id="model3",
                model_name="Model 3",
                predictions=[10.7, 11.1, 10.7, 11.4, 10.8]
            )
        ]

    @pytest.fixture
    def sample_true_values(self):
        return [10.6, 11.0, 10.9, 11.2, 10.8]

    @pytest.fixture
    def fusion_config(self):
        return FusionConfig(
            strategy=FusionStrategy.WEIGHTED_AVERAGE,
            weight_config=WeightConfig(
                method=WeightMethod.RMSE_BASED,
                min_weight=0.0,
                max_weight=1.0,
                normalize=True
            ),
            enable_cross_validation=True,
            enable_stability_check=True,
            enable_uncertainty_propagation=True,
            n_folds=5
        )

    def test_simple_average_fusion(self, engine, sample_models, fusion_config):
        """测试简单平均融合"""
        fusion_config.strategy = FusionStrategy.SIMPLE_AVERAGE
        fusion_config.weight_config.method = WeightMethod.EQUAL

        result = engine.fuse(fusion_config, sample_models)

        assert len(result.fused_predictions) == len(sample_models[0].predictions)
        assert len(result.weights) == 3
        assert result.fusion_strategy == FusionStrategy.SIMPLE_AVERAGE.value

    def test_weighted_average_fusion(self, engine, sample_models, fusion_config):
        """测试加权平均融合"""
        result = engine.fuse(fusion_config, sample_models)

        assert len(result.fused_predictions) == len(sample_models[0].predictions)
        assert len(result.weights) == 3
        assert sum(result.weights.values()) == pytest.approx(1.0)
        assert result.fusion_strategy == FusionStrategy.WEIGHTED_AVERAGE.value

    def test_median_fusion(self, engine, sample_models, fusion_config):
        """测试中位数融合"""
        fusion_config.strategy = FusionStrategy.MEDIAN
        fusion_config.weight_config.method = WeightMethod.EQUAL

        result = engine.fuse(fusion_config, sample_models)

        assert len(result.fused_predictions) == len(sample_models[0].predictions)
        assert result.fusion_strategy == FusionStrategy.MEDIAN.value

    def test_fusion_with_evaluation(self, engine, sample_models, fusion_config, sample_true_values):
        """测试带评估的融合"""
        result = engine.fuse(fusion_config, sample_models, sample_true_values)

        assert 'rmse' in result.metrics
        assert 'mae' in result.metrics
        assert 'r2' in result.metrics
        assert result.improvement is not None

    def test_compare_strategies(self, engine, sample_models, fusion_config, sample_true_values):
        """测试策略对比"""
        results = engine.compare_strategies(
            fusion_config,
            sample_models,
            sample_true_values,
            strategies=[
                FusionStrategy.SIMPLE_AVERAGE,
                FusionStrategy.WEIGHTED_AVERAGE,
                FusionStrategy.MEDIAN
            ]
        )

        assert len(results) == 3
        assert 'simple_average' in results
        assert 'weighted_average' in results
        assert 'median' in results

    def test_optimize_weights(self, engine, sample_models, fusion_config, sample_true_values):
        """测试权重优化"""
        optimization = engine.optimize_weights(
            fusion_config,
            sample_models,
            sample_true_values
        )

        assert 'results' in optimization
        assert 'best_method' in optimization
        assert 'best_rmse' in optimization
        assert optimization['best_method'] is not None


class TestIntegration:
    """集成测试"""

    def test_end_to_end_fusion(self):
        """端到端融合测试"""
        from app.model_fusion.services.fusion_service import FusionService

        service = FusionService()

        # 创建测试数据
        models = [
            {
                'model_id': 'model1',
                'model_name': 'Model 1',
                'predictions': [10.5, 11.2, 10.8, 11.5, 10.9]
            },
            {
                'model_id': 'model2',
                'model_name': 'Model 2',
                'predictions': [10.8, 11.0, 10.9, 11.3, 11.1]
            },
            {
                'model_id': 'model3',
                'model_name': 'Model 3',
                'predictions': [10.7, 11.1, 10.7, 11.4, 10.8]
            }
        ]

        config = {
            'strategy': 'weighted_average',
            'weight_method': 'rmse_based',
            'min_weight': 0.0,
            'max_weight': 1.0,
            'normalize': True
        }

        true_values = [10.6, 11.0, 10.9, 11.2, 10.8]

        # 创建任务
        task_id = service.create_fusion_task(models, config, true_values)
        assert task_id is not None

        # 检查状态
        import time
        for _ in range(10):
            status = service.get_task_status(task_id)
            if status['status'] in ['completed', 'failed']:
                break
            time.sleep(0.5)

        # 获取结果
        final_status = service.get_task_status(task_id)
        assert final_status['status'] == 'completed'

        result = service.get_task_result(task_id)
        assert result is not None
        assert 'fused_predictions' in result
        assert 'weights' in result
        assert 'metrics' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
