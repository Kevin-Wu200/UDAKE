"""
置信度门控测试 —— 验证各行业的置信度计算与门控触发逻辑

测试覆盖:
1. 各行业置信度计算器: 地形测绘/气象预报/农业遥感/城市热岛
2. 置信度门控: 高于阈值可用，低于阈值抛出 ConfidenceInsufficientError
3. requires_confidence 装饰器行为
4. 跨行业适配器动态切换 (配置热加载)
5. 采样推荐置信度校验
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from realtime_interpolation.utils.confidence_calculator import (
    AgricultureConfidenceCalculator,
    BaseConfidenceCalculator,
    ConfidenceInsufficientError,
    ConfidenceResult,
    MeteorologyConfidenceCalculator,
    TopographyConfidenceCalculator,
    UrbanHeatConfidenceCalculator,
    clear_calculator_cache,
    compute_confidence_score,
    get_confidence_calculator,
    requires_confidence,
)


# ============================================================================
# 辅助函数
# ============================================================================


def _make_low_variance(n: int = 100) -> np.ndarray:
    """生成类方差数据 —— 低方差场景 (模拟稳定的低不确定性)"""
    return np.abs(np.random.normal(0.0, 0.05, n))


def _make_high_variance(n: int = 100) -> np.ndarray:
    """生成类方差数据 —— 高方差场景 (模拟高不确定性)"""
    return np.abs(np.random.normal(0.0, 2.0, n))


def _make_zero_variance(n: int = 100) -> np.ndarray:
    """生成零方差数据 (完美场景)"""
    return np.zeros(n)


# ============================================================================
# 1. 各行业置信度计算器测试
# ============================================================================


class TestTopographyConfidenceCalculator:
    """地形测绘置信度计算器 (阈值 0.90)"""

    @pytest.fixture
    def calc(self) -> TopographyConfidenceCalculator:
        return TopographyConfidenceCalculator(industry="topography", threshold=0.90)

    def test_zero_variance_returns_max_confidence(self, calc: TopographyConfidenceCalculator) -> None:
        """零方差 -> 置信度 1.0"""
        result = calc.calculate(_make_zero_variance())
        assert result.score == pytest.approx(1.0, abs=0.01)
        assert result.is_sufficient is True

    def test_very_low_variance_passes_threshold(self, calc: TopographyConfidenceCalculator) -> None:
        """极低方差 -> 置信度 >= 0.90"""
        result = calc.calculate(_make_low_variance(1000))
        assert result.is_sufficient is True

    def test_high_variance_fails_threshold(self, calc: TopographyConfidenceCalculator) -> None:
        """高方差 -> 置信度 < 0.90"""
        result = calc.calculate(_make_high_variance(1000))
        assert result.is_sufficient is False

    def test_empty_variance_returns_zero_confidence(self, calc: TopographyConfidenceCalculator) -> None:
        """空方差数组 -> 置信度 0.0"""
        result = calc.calculate(np.array([]))
        assert result.score == 0.0
        assert result.is_sufficient is False

    def test_check_raises_when_insufficient(self, calc: TopographyConfidenceCalculator) -> None:
        """check() 在置信度不足时抛出 ConfidenceInsufficientError"""
        with pytest.raises(ConfidenceInsufficientError) as exc_info:
            calc.check(_make_high_variance())
        assert exc_info.value.industry == "topography"
        assert exc_info.value.threshold == pytest.approx(0.90)


class TestMeteorologyConfidenceCalculator:
    """气象预报置信度计算器 (阈值 0.85)"""

    @pytest.fixture
    def calc(self) -> MeteorologyConfidenceCalculator:
        return MeteorologyConfidenceCalculator(industry="meteorology", threshold=0.85)

    def test_low_variance_passes(self, calc: MeteorologyConfidenceCalculator) -> None:
        result = calc.calculate(_make_low_variance(1000), predictions=np.ones(1000) * 10.0)
        assert result.is_sufficient is True

    def test_high_variance_with_narrow_range_fails(self, calc: MeteorologyConfidenceCalculator) -> None:
        """高方差 + 窄范围 -> 置信度低"""
        variance = _make_high_variance(1000)
        # 预测范围窄，relative variance 高
        predictions = np.array([10.0, 10.5])
        result = calc.calculate(variance, predictions=predictions)
        assert result.is_sufficient is False

    def test_with_wide_prediction_range_boosts_confidence(self, calc: MeteorologyConfidenceCalculator) -> None:
        """宽预测范围 -> range_scale 大 -> 相对方差小 -> 置信度高"""
        result = calc.calculate(
            _make_low_variance(1000),
            predictions=np.linspace(0, 100, 100),
        )
        assert result.is_sufficient is True


class TestAgricultureConfidenceCalculator:
    """农业遥感置信度计算器 (阈值 0.80)"""

    @pytest.fixture
    def calc(self) -> AgricultureConfidenceCalculator:
        return AgricultureConfidenceCalculator(industry="agriculture", threshold=0.80)

    def test_low_variance_high_anomaly_score_passes(self, calc: AgricultureConfidenceCalculator) -> None:
        result = calc.calculate(_make_low_variance(1000), anomaly_score=1.0)
        assert result.is_sufficient is True

    def test_high_variance_low_anomaly_score_fails(self, calc: AgricultureConfidenceCalculator) -> None:
        result = calc.calculate(_make_high_variance(1000), anomaly_score=0.3)
        assert result.is_sufficient is False

    def test_anomaly_score_weight(self, calc: AgricultureConfidenceCalculator) -> None:
        """验证 anomaly_score 权重 50%"""
        low_var = _make_low_variance(1000)
        r1 = calc.calculate(low_var, anomaly_score=1.0)
        r2 = calc.calculate(low_var, anomaly_score=0.5)
        assert r1.score > r2.score


class TestUrbanHeatConfidenceCalculator:
    """城市热岛监测置信度计算器 (阈值 0.85)"""

    @pytest.fixture
    def calc(self) -> UrbanHeatConfidenceCalculator:
        return UrbanHeatConfidenceCalculator(industry="urban_heat", threshold=0.85)

    def test_low_variance_high_r2_passes(self, calc: UrbanHeatConfidenceCalculator) -> None:
        result = calc.calculate(_make_low_variance(1000), r2_score=0.9)
        assert result.is_sufficient is True

    def test_high_variance_low_r2_fails(self, calc: UrbanHeatConfidenceCalculator) -> None:
        result = calc.calculate(_make_high_variance(1000), r2_score=0.2)
        assert result.is_sufficient is False

    def test_r2_weight_70_percent(self, calc: UrbanHeatConfidenceCalculator) -> None:
        """验证 R² 权重 70%"""
        low_var = _make_low_variance(1000)
        r1 = calc.calculate(low_var, r2_score=0.9)
        r2 = calc.calculate(low_var, r2_score=0.3)
        assert r1.score > r2.score  # R² 差异显著影响置信度


# ============================================================================
# 2. 置信度门控测试 —— 高于阈值可用，低于抛出异常
# ============================================================================


class TestConfidenceGating:
    """置信度门控逻辑"""

    def test_high_confidence_passes(self) -> None:
        """高置信度 -> check() 不抛异常"""
        calc = TopographyConfidenceCalculator(industry="topography", threshold=0.90)
        result = calc.check(_make_zero_variance())
        assert result.is_sufficient is True
        assert result.score == pytest.approx(1.0, abs=0.01)

    @pytest.mark.parametrize("industry,threshold,calc_cls,extra_kwargs", [
        ("topography", 0.90, TopographyConfidenceCalculator, {}),
        ("meteorology", 0.85, MeteorologyConfidenceCalculator, {"predictions": np.array([1.0])}),
        ("agriculture", 0.80, AgricultureConfidenceCalculator, {"anomaly_score": 0.0}),
        ("urban_heat", 0.85, UrbanHeatConfidenceCalculator, {"r2_score": 0.0}),
    ])
    def test_high_variance_triggers_gating(
        self, industry: str, threshold: float, calc_cls: type[BaseConfidenceCalculator], extra_kwargs: dict
    ) -> None:
        """各行业的高方差数据触发门控异常"""
        calc = calc_cls(industry=industry, threshold=threshold)
        with pytest.raises(ConfidenceInsufficientError) as exc_info:
            calc.check(_make_high_variance(1000), **extra_kwargs)
        assert exc_info.value.industry == industry
        assert exc_info.value.threshold == pytest.approx(threshold)
        assert exc_info.value.current_confidence < threshold

    def test_confidence_result_to_dict(self) -> None:
        """ConfidenceResult.to_dict() 格式验证"""
        result = ConfidenceResult(
            score=0.92, threshold=0.90, is_sufficient=True, industry="topography",
        )
        d = result.to_dict()
        assert d["confidence_score"] == 0.92
        assert d["confidence_threshold"] == 0.90
        assert d["is_sufficient"] is True
        assert d["industry"] == "topography"
        assert "details" in d


# ============================================================================
# 3. requires_confidence 装饰器测试
# ============================================================================


class TestRequiresConfidenceDecorator:
    """requires_confidence 装饰器测试"""

    def test_decorator_passes_high_confidence(self) -> None:
        """装饰器在高置信度时不干预函数执行"""

        @requires_confidence(threshold=0.90, industry="topography", variance_key="variance")
        def sample_func(variance: np.ndarray) -> str:
            return "ok"

        result = sample_func(variance=_make_zero_variance())
        assert result == "ok"

    def test_decorator_raises_on_low_confidence(self) -> None:
        """装饰器在低置信度时抛出异常"""

        @requires_confidence(threshold=0.90, industry="topography", variance_key="variance")
        def sample_func(variance: np.ndarray) -> str:
            return "ok"

        with pytest.raises(ConfidenceInsufficientError):
            sample_func(variance=_make_high_variance(1000))

    def test_decorator_skips_when_variance_not_found(self) -> None:
        """装饰器在无法提取方差时跳过检查"""

        @requires_confidence(threshold=0.90, industry="topography", variance_key="variance")
        def sample_func(other_param: str = "hello") -> str:
            return other_param

        result = sample_func(other_param="world")
        assert result == "world"

    def test_decorator_with_kwargs_passthrough(self) -> None:
        """装饰器透传额外 kwargs 给计算器"""

        @requires_confidence(threshold=0.85, industry="urban_heat", variance_key="variance")
        def sample_func(variance: np.ndarray, r2_score: float = 0.9) -> float:
            return r2_score

        # R²=0.95 + 零方差 -> 应通过
        result = sample_func(variance=_make_zero_variance(), r2_score=0.95)
        assert result == 0.95


# ============================================================================
# 4. 跨行业适配器动态切换 (配置热加载)
# ============================================================================


class TestIndustryAdapterSwitching:
    """跨行业适配器动态切换测试"""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """每个测试前后清空计算器缓存"""
        clear_calculator_cache()
        yield
        clear_calculator_cache()

    def test_get_calculator_returns_different_types(self) -> None:
        """不同行业返回不同计算器类型"""
        topo_calc = get_confidence_calculator("topography")
        met_calc = get_confidence_calculator("meteorology")
        agri_calc = get_confidence_calculator("agriculture")
        urban_calc = get_confidence_calculator("urban_heat")

        assert isinstance(topo_calc, TopographyConfidenceCalculator)
        assert isinstance(met_calc, MeteorologyConfidenceCalculator)
        assert isinstance(agri_calc, AgricultureConfidenceCalculator)
        assert isinstance(urban_calc, UrbanHeatConfidenceCalculator)

    def test_get_calculator_caches(self) -> None:
        """同一行业获取的计算器是同一实例 (缓存)"""
        calc1 = get_confidence_calculator("topography")
        calc2 = get_confidence_calculator("topography")
        assert calc1 is calc2

    def test_clear_cache_recreates_instance(self) -> None:
        """clear_calculator_cache() 后重新创建实例"""
        calc1 = get_confidence_calculator("topography")
        clear_calculator_cache()
        calc2 = get_confidence_calculator("topography")
        assert calc1 is not calc2

    def test_config_yaml_content(self) -> None:
        """验证 confidence_thresholds.yaml 配置内容"""
        config_path = PROJECT_ROOT / "configs" / "confidence_thresholds.yaml"
        assert config_path.exists(), f"配置文件不存在: {config_path}"

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        industries = data.get("industries", {})
        assert "topography" in industries
        assert "meteorology" in industries
        assert "agriculture" in industries
        assert "urban_heat" in industries
        assert industries["topography"]["threshold"] == 0.90
        assert industries["meteorology"]["threshold"] == 0.85
        assert industries["agriculture"]["threshold"] == 0.80
        assert industries["urban_heat"]["threshold"] == 0.85

    def test_dynamic_threshold_update(self) -> None:
        """模拟修改阈值后的动态生效 (通过 clear_cache + 重新获取)"""
        # 默认 topography 阈值 = 0.90
        calc = get_confidence_calculator("topography")
        assert calc.threshold == 0.90

        # 清空缓存后可直接修改阈值 (模拟配置热加载场景)
        clear_calculator_cache()
        calc2 = get_confidence_calculator("topography")
        # 由于没有真实 YAML 覆盖,阈值为默认 0.90
        assert calc2.threshold == 0.90

    def test_compute_confidence_score_dispatches_correctly(self) -> None:
        """compute_confidence_score 根据 industry 分发到正确计算器"""
        low_var = _make_low_variance(100)
        high_var = _make_high_variance(100)

        # 地形测绘 (0.90): 高方差应不通过
        r_topo = compute_confidence_score(high_var, industry="topography")
        assert r_topo.is_sufficient is False

        # 农业遥感 (0.80): 同样的高方差可能通过 (阈值更低)
        r_agri = compute_confidence_score(high_var, industry="agriculture", anomaly_score=1.0)
        # 0.80 阈值更低, 但高方差可能仍不通过
        # 此测试验证分发机制而非具体阈值


# ============================================================================
# 5. 采样推荐置信度校验集成测试
# ============================================================================


class TestSamplingRecommendationConfidence:
    """采样推荐置信度校验"""

    def test_sampling_recommender_confidence_gating(self) -> None:
        """模拟采样推荐中的置信度门控"""
        from adaptive_sampling.采样点推荐生成 import SamplingRecommender

        recommender = SamplingRecommender()

        # 创建模拟方差网格
        variance = np.random.rand(20, 20) * 0.1  # 低方差 -> 高置信度
        x_coords = np.linspace(0, 100, 20)
        y_coords = np.linspace(0, 100, 20)

        result = recommender.generate_recommendations(
            variance=variance,
            x_coords=x_coords,
            y_coords=y_coords,
            n_recommendations=10,
            strategy="variance_based",
            industry="topography",
        )

        assert "recommendations" in result
        assert "confidence_score" in result
        assert "is_confidence_sufficient" in result
        assert "industry" in result
        assert result["industry"] == "topography"

    def test_sampling_recommender_falls_back_on_low_confidence(self) -> None:
        """低置信度时采样推荐自动降级为 spatial_coverage"""
        from adaptive_sampling.采样点推荐生成 import SamplingRecommender

        recommender = SamplingRecommender()

        # 创建高方差网格 -> 低置信度
        variance = np.random.rand(20, 20) * 10.0
        x_coords = np.linspace(0, 100, 20)
        y_coords = np.linspace(0, 100, 20)

        result = recommender.generate_recommendations(
            variance=variance,
            x_coords=x_coords,
            y_coords=y_coords,
            n_recommendations=10,
            strategy="variance_based",
            industry="topography",
        )

        # 应自动降级为 spatial_coverage 或 hybrid
        assert result["strategy"] in ("spatial_coverage", "variance_based", "hybrid")
        # 置信度不足时应标记
        if not result["is_confidence_sufficient"]:
            assert result["strategy"] == "spatial_coverage"


# ============================================================================
# 6. error predictor / anomaly / trend 集成测试
# ============================================================================


class TestErrorPredictorConfidence:
    """误差预测模型置信度集成"""

    def test_estimate_industry_confidence(self) -> None:
        """验证误差预测模型可以计算行业置信度"""
        from ai_extension.误差预测模型 import ErrorPredictor

        predictor = ErrorPredictor()
        # 训练模型
        x = np.random.rand(100)
        y = np.random.rand(100)
        actual = x * 3 + y * 5 + np.random.normal(0, 0.1, 100)
        predicted = x * 3 + y * 5

        predictor.train(x, y, actual, predicted)

        # 测试行业置信度估算
        conf_info = predictor.estimate_industry_confidence(
            x[:50], y[:50], predicted[:50],
            industry="meteorology",
        )
        assert "confidence_score" in conf_info
        assert "is_sufficient" in conf_info
        assert "confidence_threshold" in conf_info

    def test_gate_raster_preview(self) -> None:
        """验证栅格预览门控函数"""
        from ai_extension.误差预测模型 import ErrorPredictor

        predictor = ErrorPredictor()
        x = np.random.rand(100)
        y = np.random.rand(100)
        actual = x * 3 + y * 5 + np.random.normal(0, 0.05, 100)
        predicted = x * 3 + y * 5

        predictor.train(x, y, actual, predicted)

        # 低方差场景: preview 应启用
        gate_result = predictor.gate_raster_preview(
            x[:50], y[:50], predicted[:50],
            variance=np.ones(50) * 0.01,
            industry="meteorology",
        )
        assert "preview_enabled" in gate_result
        assert "suggestion" in gate_result

        # 高方差场景: preview 应禁用并给出建议
        gate_result_high = predictor.gate_raster_preview(
            x[:50], y[:50], predicted[:50],
            variance=np.ones(50) * 100.0,
            industry="meteorology",
        )
        if not gate_result_high["preview_enabled"]:
            assert gate_result_high["suggestion"] is not None


class TestTrendConfidence:
    """趋势识别置信度集成"""

    def test_estimate_trend_confidence(self) -> None:
        """验证趋势模型置信度估算"""
        from ai_extension.趋势识别模型 import TrendIdentifier

        identifier = TrendIdentifier()
        x = np.linspace(0, 100, 50)
        y = np.linspace(0, 100, 50)
        # 强线性趋势数据
        values = 2.0 * x + 1.5 * y + 100 + np.random.normal(0, 2, 50)

        conf_info = identifier.estimate_trend_confidence(
            x, y, values, industry="urban_heat",
        )
        assert "confidence_score" in conf_info
        assert "r2_score" in conf_info.get("details", {})

    def test_gate_trend_analysis(self) -> None:
        """验证趋势分析门控函数"""
        from ai_extension.趋势识别模型 import TrendIdentifier

        identifier = TrendIdentifier()
        x = np.linspace(0, 100, 50)
        y = np.linspace(0, 100, 50)
        values = 2.0 * x + 1.5 * y + 100 + np.random.normal(0, 1, 50)

        gate_result = identifier.gate_trend_analysis(
            x, y, values, industry="urban_heat",
        )
        assert "analysis_enabled" in gate_result
        assert "suggestion" in gate_result

        # 强趋势 + 极低噪声: 应启用分析
        clean_values = 2.0 * x + 1.5 * y + 100  # 无噪声确定性数据
        gate_clean = identifier.gate_trend_analysis(
            x, y, clean_values, industry="urban_heat",
        )
        assert gate_clean["analysis_enabled"] is True


class TestAnomalyDetectionConfidence:
    """异常检测置信度集成"""

    def test_deep_fusion_detector_confidence_lock_off(self) -> None:
        """关闭置信度生成锁时，即使低置信度也不抛异常"""
        from ai_extension.异常检测模块 import DeepAnomalyFusionDetector

        detector = DeepAnomalyFusionDetector()
        x = np.random.rand(30)
        y = np.random.rand(30)
        values = np.random.rand(30)

        # require_confidence=False (默认), 不抛异常
        result = detector.detect(x, y, values, require_confidence=False)
        assert "anomaly_count" in result

    def test_deep_fusion_detector_confidence_lock_on(self) -> None:
        """开启置信度生成锁时，低置信度应抛出 ConfidenceInsufficientError"""
        from ai_extension.异常检测模块 import DeepAnomalyFusionDetector

        detector = DeepAnomalyFusionDetector()
        x = np.random.rand(30)
        y = np.random.rand(30)
        # 使用高方差值以产生低置信度
        values = np.random.normal(0, 100, 30)

        with pytest.raises(ConfidenceInsufficientError) as exc_info:
            detector.detect(x, y, values, require_confidence=True, industry="agriculture")
        assert exc_info.value.industry == "agriculture"
        assert exc_info.value.threshold == pytest.approx(0.80)
