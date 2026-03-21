"""
核心算法单元测试
测试采样点影响评估器、改进的采样推荐器和实时采样预览器
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.采样点影响评估器 import SamplingPointImpactEvaluator
from app.core.改进的采样推荐器 import ImprovedSamplingRecommender
from app.core.实时采样预览 import RealTimeSamplingPreview


class TestSamplingPointImpactEvaluator:
    """测试采样点影响评估器"""

    @pytest.fixture
    def evaluator(self):
        """创建评估器实例"""
        return SamplingPointImpactEvaluator(
            variogram_model="spherical",
            nlags=6,
            max_workers=2  # 减少工作线程数以加快测试
        )

    @pytest.fixture
    def sample_data(self):
        """创建示例数据"""
        # 创建 10 个采样点
        np.random.seed(42)
        existing_points = np.random.rand(10, 2) * 100
        existing_values = np.random.rand(10) * 10

        # 创建 5 个候选点
        candidate_points = np.random.rand(5, 2) * 100
        candidate_values = np.random.rand(5) * 10

        return {
            'existing_points': existing_points,
            'existing_values': existing_values,
            'candidate_points': candidate_points,
            'candidate_values': candidate_values
        }

    def test_evaluator_initialization(self, evaluator):
        """测试评估器初始化"""
        assert evaluator.variogram_model == "spherical"
        assert evaluator.nlags == 6
        assert evaluator.max_workers == 2

    def test_evaluate_impact_basic(self, evaluator, sample_data):
        """测试基本影响评估"""
        results = evaluator.evaluate_impact(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            candidate_points=sample_data['candidate_points'],
            candidate_values=sample_data['candidate_values'],
            grid_resolution=20  # 降低分辨率以加快测试
        )

        # 验证返回结果
        assert len(results) == 5
        for result in results:
            assert 'variance_reduction' in result
            assert 'local_improvement' in result
            assert 'comprehensive_score' in result
            assert 'influence_radius' in result
            assert 'candidate_index' in result

    def test_evaluate_impact_without_candidate_values(self, evaluator, sample_data):
        """测试没有提供候选值的情况"""
        results = evaluator.evaluate_impact(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            candidate_points=sample_data['candidate_points'],
            candidate_values=None,
            grid_resolution=20
        )

        assert len(results) == 5
        # 所有结果应该成功
        assert all('error' not in result for result in results)

    def test_evaluate_impact_single_candidate(self, evaluator, sample_data):
        """测试单个候选点的评估"""
        single_candidate = sample_data['candidate_points'][0:1]
        single_value = sample_data['candidate_values'][0:1]

        results = evaluator.evaluate_impact(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            candidate_points=single_candidate,
            candidate_values=single_value,
            grid_resolution=20
        )

        assert len(results) == 1
        assert results[0]['candidate_index'] == 0

    def test_perform_loo_validation(self, evaluator, sample_data):
        """测试留一法交叉验证"""
        results = evaluator.perform_loo_validation(
            points=sample_data['existing_points'],
            values=sample_data['existing_values']
        )

        assert 'rmse' in results
        assert 'mae' in results
        assert 'r2' in results
        assert 'n_valid' in results
        assert results['n_valid'] > 0

    def test_calculate_influence_radius(self, evaluator, sample_data):
        """测试影响半径计算"""
        radius = evaluator._calculate_influence_radius(
            existing_points=sample_data['existing_points'],
            candidate_points=sample_data['candidate_points']
        )

        assert isinstance(radius, float)
        assert radius > 0

    def test_comprehensive_score_calculation(self, evaluator):
        """测试综合评分计算"""
        score = evaluator._calculate_comprehensive_score(
            variance_reduction_ratio=0.5,
            local_improvement=0.3
        )

        assert isinstance(score, float)
        assert 0 <= score <= 1
        # 验证权重：70% 方差减少 + 30% 局部改善
        expected = 0.7 * 0.5 + 0.3 * 0.3
        assert abs(score - expected) < 0.01


class TestImprovedSamplingRecommender:
    """测试改进的采样推荐器"""

    @pytest.fixture
    def recommender(self):
        """创建推荐器实例"""
        impact_evaluator = SamplingPointImpactEvaluator(max_workers=2)
        return ImprovedSamplingRecommender(
            impact_evaluator=impact_evaluator,
            max_workers=2
        )

    @pytest.fixture
    def sample_data(self):
        """创建示例数据"""
        np.random.seed(42)
        existing_points = np.random.rand(10, 2) * 100
        existing_values = np.random.rand(10) * 10

        # 创建方差栅格
        x_coords = np.linspace(0, 100, 50)
        y_coords = np.linspace(0, 100, 50)
        xx, yy = np.meshgrid(x_coords, y_coords)
        variance_grid = np.random.rand(50, 50) * 0.1

        return {
            'existing_points': existing_points,
            'existing_values': existing_values,
            'variance_grid': variance_grid,
            'x_coords': x_coords,
            'y_coords': y_coords
        }

    def test_recommender_initialization(self, recommender):
        """测试推荐器初始化"""
        assert recommender.impact_evaluator is not None
        assert recommender.max_workers == 2

    def test_recommend_by_impact(self, recommender, sample_data):
        """测试基于影响的推荐"""
        results = recommender.recommend_optimal_points(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            variance_grid=sample_data['variance_grid'],
            x_coords=sample_data['x_coords'],
            y_coords=sample_data['y_coords'],
            n_recommendations=5,
            strategy="impact_optimized"
        )

        assert 'strategy' in results
        assert 'n_recommendations' in results
        assert 'recommendations' in results
        assert results['strategy'] == "impact_optimized"
        assert len(results['recommendations']) <= 5

    def test_recommend_by_variance(self, recommender, sample_data):
        """测试基于方差的推荐"""
        results = recommender.recommend_optimal_points(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            variance_grid=sample_data['variance_grid'],
            x_coords=sample_data['x_coords'],
            y_coords=sample_data['y_coords'],
            n_recommendations=5,
            strategy="variance_based"
        )

        assert results['strategy'] == "variance_based"
        assert len(results['recommendations']) <= 5

    def test_recommend_by_coverage(self, recommender, sample_data):
        """测试基于覆盖的推荐"""
        results = recommender.recommend_optimal_points(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            variance_grid=sample_data['variance_grid'],
            x_coords=sample_data['x_coords'],
            y_coords=sample_data['y_coords'],
            n_recommendations=5,
            strategy="spatial_coverage"
        )

        assert results['strategy'] == "spatial_coverage"
        assert len(results['recommendations']) <= 5

    def test_recommend_hybrid(self, recommender, sample_data):
        """测试混合策略推荐"""
        results = recommender.recommend_optimal_points(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            variance_grid=sample_data['variance_grid'],
            x_coords=sample_data['x_coords'],
            y_coords=sample_data['y_coords'],
            n_recommendations=10,
            strategy="hybrid"
        )

        assert results['strategy'] == "hybrid"
        # 混合策略应该返回约10个点（6个影响 + 4个覆盖）
        assert len(results['recommendations']) <= 10

    def test_recommend_with_constraints(self, recommender, sample_data):
        """测试带约束条件的推荐"""
        constraints = {
            'min_distance': 10.0,
            'max_points_per_region': 3
        }

        results = recommender.recommend_optimal_points(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            variance_grid=sample_data['variance_grid'],
            x_coords=sample_data['x_coords'],
            y_coords=sample_data['y_coords'],
            n_recommendations=5,
            strategy="impact_optimized",
            constraints=constraints
        )

        # 验证约束被应用
        assert 'constraints_applied' in results
        assert len(results['recommendations']) <= 3  # max_points_per_region

    def test_select_diverse_points(self, recommender):
        """测试多样化点选择"""
        candidates = [
            {'x': 10.0, 'y': 10.0, 'comprehensive_score': 0.9, 'variance': 0.5},
            {'x': 12.0, 'y': 12.0, 'comprehensive_score': 0.8, 'variance': 0.4},
            {'x': 50.0, 'y': 50.0, 'comprehensive_score': 0.7, 'variance': 0.3},
            {'x': 52.0, 'y': 52.0, 'comprehensive_score': 0.6, 'variance': 0.2},
        ]

        selected = recommender._select_diverse_points(
            candidates, n=2, min_distance=5.0
        )

        assert len(selected) <= 2
        # 验证选择的点满足最小距离约束
        if len(selected) >= 2:
            pos1 = np.array([selected[0]['x'], selected[0]['y']])
            pos2 = np.array([selected[1]['x'], selected[1]['y']])
            distance = np.linalg.norm(pos1 - pos2)
            assert distance >= 5.0

    def test_rank_by_comprehensive_score(self, recommender):
        """测试按综合评分排序"""
        candidates = [
            {'x': 10.0, 'y': 10.0, 'variance_reduction_ratio': 0.5, 'local_improvement': 0.3},
            {'x': 20.0, 'y': 20.0, 'variance_reduction_ratio': 0.7, 'local_improvement': 0.4},
            {'x': 30.0, 'y': 30.0, 'variance_reduction_ratio': 0.3, 'local_improvement': 0.2},
        ]

        ranked = recommender.rank_by_comprehensive_score(candidates)

        assert len(ranked) == 3
        # 验证按综合评分降序排序
        scores = [c['comprehensive_score'] for c in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_unknown_strategy(self, recommender, sample_data):
        """测试未知策略"""
        results = recommender.recommend_optimal_points(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            variance_grid=sample_data['variance_grid'],
            x_coords=sample_data['x_coords'],
            y_coords=sample_data['y_coords'],
            n_recommendations=5,
            strategy="unknown_strategy"
        )

        # 应该回退到默认策略
        assert results['strategy'] == "unknown_strategy"


class TestRealTimeSamplingPreview:
    """测试实时采样预览器"""

    @pytest.fixture
    def preview(self):
        """创建预览器实例"""
        return RealTimeSamplingPreview(
            variogram_model="spherical",
            nlags=6
        )

    @pytest.fixture
    def sample_data(self):
        """创建示例数据"""
        np.random.seed(42)
        existing_points = np.random.rand(10, 2) * 100
        existing_values = np.random.rand(10) * 10
        new_point = np.array([50.0, 50.0])
        new_value = 5.0

        return {
            'existing_points': existing_points,
            'existing_values': existing_values,
            'new_point': new_point,
            'new_value': new_value
        }

    def test_preview_initialization(self, preview):
        """测试预览器初始化"""
        assert preview.variogram_model == "spherical"
        assert preview.nlags == 6
        assert preview.impact_evaluator is not None

    def test_preview_sampling_effect_basic(self, preview, sample_data):
        """测试基本采样效果预览"""
        results = preview.preview_sampling_effect(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            new_point=sample_data['new_point'],
            new_value=sample_data['new_value'],
            grid_resolution=20  # 降低分辨率以加快测试
        )

        # 验证返回结果
        assert 'variance_reduction_map' in results
        assert 'total_variance_reduction' in results
        assert 'variance_reduction_ratio' in results
        assert 'influence_radius' in results
        assert 'improved_regions' in results
        assert 'quantitative_metrics' in results

    def test_preview_with_variance_grid(self, preview, sample_data):
        """测试带方差栅格的预览"""
        x_coords = np.linspace(0, 100, 20)
        y_coords = np.linspace(0, 100, 20)
        variance_grid = np.random.rand(20, 20) * 0.1

        results = preview.preview_sampling_effect(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            new_point=sample_data['new_point'],
            new_value=sample_data['new_value'],
            grid_resolution=20,
            variance_grid=variance_grid,
            x_coords=x_coords,
            y_coords=y_coords
        )

        assert 'variance_reduction_map' in results

    def test_influence_radius_calculation(self, preview):
        """测试影响半径计算"""
        existing_points = np.random.rand(5, 2) * 100
        new_point = np.array([50.0, 50.0])
        variance_reduction = np.random.rand(20, 20) * 0.05

        grid_x = np.linspace(0, 100, 20)
        grid_y = np.linspace(0, 100, 20)

        radius = preview._calculate_influence_radius(
            existing_points=existing_points,
            new_point=new_point,
            variance_reduction=variance_reduction,
            grid_x=grid_x,
            grid_y=grid_y
        )

        assert isinstance(radius, float)
        assert radius >= 0

    def test_identify_improved_regions(self, preview):
        """测试改善区域识别"""
        variance_reduction = np.random.rand(20, 20) * 0.05
        grid_x = np.linspace(0, 100, 20)
        grid_y = np.linspace(0, 100, 20)
        influence_radius = 10.0

        regions = preview._identify_improved_regions(
            variance_reduction=variance_reduction,
            grid_x=grid_x,
            grid_y=grid_y,
            influence_radius=influence_radius,
            threshold=0.3
        )

        assert isinstance(regions, list)

    def test_quantitative_metrics(self, preview, sample_data):
        """测试量化指标计算"""
        results = preview.preview_sampling_effect(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            new_point=sample_data['new_point'],
            new_value=sample_data['new_value'],
            grid_resolution=20
        )

        metrics = results['quantitative_metrics']
        assert 'rmse_improvement' in metrics
        assert 'variance_reduction_percent' in metrics
        assert 'coverage_area' in metrics
        assert 'average_improvement' in metrics

    def test_preview_multiple_points(self, preview, sample_data):
        """测试预览多个新点"""
        new_points = np.random.rand(3, 2) * 100
        new_values = np.random.rand(3) * 10

        results = preview.preview_multiple_points(
            existing_points=sample_data['existing_points'],
            existing_values=sample_data['existing_values'],
            new_points=new_points,
            new_values=new_values,
            grid_resolution=20
        )

        assert 'variance_reduction_map' in results
        assert 'total_variance_reduction' in results
        assert 'number_of_points' in results
        assert results['number_of_points'] == 3


class TestEdgeCases:
    """测试边界情况和异常处理"""

    @pytest.fixture
    def evaluator(self):
        return SamplingPointImpactEvaluator(max_workers=2)

    def test_empty_candidate_points(self, evaluator):
        """测试空候选点列表"""
        existing_points = np.random.rand(10, 2) * 100
        existing_values = np.random.rand(10) * 10
        candidate_points = np.array([]).reshape(0, 2)

        results = evaluator.evaluate_impact(
            existing_points=existing_points,
            existing_values=existing_values,
            candidate_points=candidate_points,
            grid_resolution=20
        )

        assert len(results) == 0

    def test_single_existing_point(self, evaluator):
        """测试只有一个现有点的情况"""
        existing_points = np.array([[50.0, 50.0]])
        existing_values = np.array([5.0])
        candidate_points = np.random.rand(5, 2) * 100

        results = evaluator.evaluate_impact(
            existing_points=existing_points,
            existing_values=existing_values,
            candidate_points=candidate_points,
            grid_resolution=20
        )

        # 应该能够处理，但可能效果有限
        assert len(results) == 5

    def test_all_same_values(self, evaluator):
        """测试所有值相同的情况"""
        existing_points = np.random.rand(10, 2) * 100
        existing_values = np.ones(10) * 5.0
        candidate_points = np.random.rand(5, 2) * 100

        results = evaluator.evaluate_impact(
            existing_points=existing_points,
            existing_values=existing_values,
            candidate_points=candidate_points,
            grid_resolution=20
        )

        # 应该能够处理
        assert len(results) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])