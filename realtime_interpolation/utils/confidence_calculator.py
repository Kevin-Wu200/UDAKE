"""
置信度计算模块 - 统一的置信度计算接口与门控逻辑

提供跨行业的置信度计算协议，包括:
- 置信度计算器基类
- 行业专属置信度计算器
- ConfidenceInsufficientError 异常
- requires_confidence 装饰器
- 置信度配置热加载
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 异常类
# ---------------------------------------------------------------------------


class ConfidenceInsufficientError(Exception):
    """置信度不足异常 —— 当预测置信度低于行业阈值时抛出"""

    def __init__(
        self,
        current_confidence: float,
        threshold: float,
        industry: str,
        message: str | None = None,
    ) -> None:
        self.current_confidence = current_confidence
        self.threshold = threshold
        self.industry = industry
        super().__init__(
            message
            or f"置信度不足: 当前={current_confidence:.3f}, 行业'{industry}'要求≥{threshold:.2f}"
        )


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class ConfidenceResult:
    """标准化置信度计算结果"""

    score: float  # 0.0 ~ 1.0，越高越可信
    threshold: float  # 行业要求的阈值
    is_sufficient: bool  # 是否达到阈值
    industry: str = "unknown"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_score": self.score,
            "confidence_threshold": self.threshold,
            "is_sufficient": self.is_sufficient,
            "industry": self.industry,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# 置信度计算器基类
# ---------------------------------------------------------------------------


class BaseConfidenceCalculator(ABC):
    """置信度计算器抽象基类"""

    def __init__(self, industry: str = "unknown", threshold: float = 0.75) -> None:
        self.industry = industry
        self.threshold = threshold

    @abstractmethod
    def calculate(self, variance: Any, **kwargs: Any) -> ConfidenceResult:
        """根据方差数据计算置信度"""

    def check(self, variance: Any, **kwargs: Any) -> ConfidenceResult:
        """计算并检查置信度是否达标"""
        result = self.calculate(variance, **kwargs)
        if not result.is_sufficient:
            raise ConfidenceInsufficientError(
                current_confidence=result.score,
                threshold=self.threshold,
                industry=self.industry,
            )
        return result


# ---------------------------------------------------------------------------
# 行业专属置信度计算器
# ---------------------------------------------------------------------------


class TopographyConfidenceCalculator(BaseConfidenceCalculator):
    """地形测绘置信度计算器 —— 阈值 0.90

    基于空间插值方差的归一化度量:
    confidence = 1 - mean(variance) / (reference_scale + mean(variance))
    reference_scale 默认为 1.0，可通过 kwargs 传入
    零方差场景（所有值相同）视为完全置信 (1.0)
    """

    def calculate(self, variance: Any, **kwargs: Any) -> ConfidenceResult:
        import numpy as np

        var_arr = np.asarray(variance, dtype=float)
        if var_arr.size == 0:
            return ConfidenceResult(
                score=0.0, threshold=self.threshold,
                is_sufficient=False, industry=self.industry,
            )
        mean_var = float(np.mean(var_arr))
        # 零方差场景: 所有值完全相同 => 完全置信
        if float(np.ptp(var_arr)) < 1e-10:
            return ConfidenceResult(
                score=1.0, threshold=self.threshold,
                is_sufficient=True, industry=self.industry,
                details={"mean_variance": 0.0, "max_variance": 0.0},
            )
        # 使用参考尺度归一化，避免分布形状影响
        reference_scale = float(kwargs.get("reference_scale", 1.0))
        score = float(np.clip(1.0 - mean_var / (reference_scale + mean_var), 0.0, 1.0))
        return ConfidenceResult(
            score=score,
            threshold=self.threshold,
            is_sufficient=score >= self.threshold,
            industry=self.industry,
            details={"mean_variance": mean_var, "max_variance": float(var_arr.max())},
        )


class MeteorologyConfidenceCalculator(BaseConfidenceCalculator):
    """气象预报置信度计算器 —— 阈值 0.85

    基于输出方差与误差预测的综合度量:
    confidence = 1 - sqrt(mean_variance) / (1e-8 + range_scale)
    当预测范围过窄时使用 mean(|pred|) 作为替代尺度
    """

    def calculate(self, variance: Any, **kwargs: Any) -> ConfidenceResult:
        import numpy as np

        var_arr = np.asarray(variance, dtype=float)
        if var_arr.size == 0:
            return ConfidenceResult(
                score=0.0, threshold=self.threshold,
                is_sufficient=False, industry=self.industry,
            )
        mean_var = float(np.mean(var_arr))
        # 使用预测值范围作为归一化尺度
        predictions = kwargs.get("predictions")
        range_scale = 1.0
        if predictions is not None:
            pred_arr = np.asarray(predictions, dtype=float)
            if pred_arr.size > 0:
                ptp_val = float(np.ptp(pred_arr))
                range_scale = ptp_val if ptp_val > 1e-10 else float(np.mean(np.abs(pred_arr))) + 1e-8
        score = float(np.clip(1.0 - np.sqrt(mean_var) / max(range_scale, 1e-8), 0.0, 1.0))
        return ConfidenceResult(
            score=score,
            threshold=self.threshold,
            is_sufficient=score >= self.threshold,
            industry=self.industry,
            details={"mean_variance": mean_var, "range_scale": range_scale},
        )


class AgricultureConfidenceCalculator(BaseConfidenceCalculator):
    """农业遥感置信度计算器 —— 阈值 0.80

    基于异常检测分数与方差的综合度量:
    confidence = 0.5 * anomaly_score + 0.5 * (1 - normalized_variance)
    """

    def calculate(self, variance: Any, **kwargs: Any) -> ConfidenceResult:
        import numpy as np

        var_arr = np.asarray(variance, dtype=float)
        if var_arr.size == 0:
            return ConfidenceResult(
                score=0.0, threshold=self.threshold,
                is_sufficient=False, industry=self.industry,
            )
        var_max = var_arr.max()
        if var_max < 1e-10:
            norm_var = 0.0
        else:
            norm_var = float(np.mean(var_arr) / var_max)

        # 异常检测分数: 1.0 表示无异常
        anomaly_score = float(kwargs.get("anomaly_score", 1.0))
        anomaly_score = np.clip(anomaly_score, 0.0, 1.0)

        score = float(np.clip(0.5 * anomaly_score + 0.5 * (1.0 - norm_var), 0.0, 1.0))
        return ConfidenceResult(
            score=score,
            threshold=self.threshold,
            is_sufficient=score >= self.threshold,
            industry=self.industry,
            details={
                "mean_variance": float(np.mean(var_arr)),
                "anomaly_score": anomaly_score,
            },
        )


class UrbanHeatConfidenceCalculator(BaseConfidenceCalculator):
    """城市热岛监测置信度计算器 —— 阈值 0.85

    基于趋势模型 R² 和方差的综合度量:
    confidence = 0.7 * r2_score + 0.3 * (1 - normalized_variance)
    """

    def calculate(self, variance: Any, **kwargs: Any) -> ConfidenceResult:
        import numpy as np

        var_arr = np.asarray(variance, dtype=float)
        if var_arr.size == 0:
            return ConfidenceResult(
                score=0.0, threshold=self.threshold,
                is_sufficient=False, industry=self.industry,
            )
        var_max = var_arr.max()
        if var_max < 1e-10:
            norm_var = 0.0
        else:
            norm_var = float(np.mean(var_arr) / var_max)

        # 趋势模型的 R² 分数
        r2_score = float(kwargs.get("r2_score", 0.0))
        r2_score = np.clip(r2_score, 0.0, 1.0)

        score = float(np.clip(0.7 * r2_score + 0.3 * (1.0 - norm_var), 0.0, 1.0))
        return ConfidenceResult(
            score=score,
            threshold=self.threshold,
            is_sufficient=score >= self.threshold,
            industry=self.industry,
            details={
                "mean_variance": float(np.mean(var_arr)),
                "r2_score": r2_score,
            },
        )


# ---------------------------------------------------------------------------
# 置信度计算器注册表
# ---------------------------------------------------------------------------

_calculator_registry: dict[str, BaseConfidenceCalculator] = {}


def get_confidence_calculator(
    industry: str,
    config_path: str | Path | None = None,
) -> BaseConfidenceCalculator:
    """获取指定行业的置信度计算器 (带缓存)"""
    if industry in _calculator_registry:
        return _calculator_registry[industry]

    # 从配置文件加载阈值
    threshold_map = _load_thresholds_from_config(config_path)
    threshold = threshold_map.get(industry, 0.75)

    calculator_map: dict[str, type[BaseConfidenceCalculator]] = {
        "topography": TopographyConfidenceCalculator,
        "meteorology": MeteorologyConfidenceCalculator,
        "agriculture": AgricultureConfidenceCalculator,
        "urban_heat": UrbanHeatConfidenceCalculator,
    }

    calc_cls = calculator_map.get(industry, BaseConfidenceCalculator)
    calc = calc_cls(industry=industry, threshold=threshold)
    _calculator_registry[industry] = calc
    return calc


def _load_thresholds_from_config(config_path: str | Path | None = None) -> dict[str, float]:
    """从 YAML 配置文件加载行业置信度阈值"""
    if config_path is None:
        # 查找默认配置文件路径
        candidates = [
            Path("configs/confidence_thresholds.yaml"),
            Path(__file__).parent.parent.parent / "configs" / "confidence_thresholds.yaml",
        ]
        for p in candidates:
            if p.exists():
                config_path = p
                break

    if config_path is None or not Path(config_path).exists():
        logger.warning("置信度配置文件未找到，使用默认阈值")
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        thresholds: dict[str, float] = {}
        industries = data.get("industries", {})
        for key, cfg in industries.items():
            if isinstance(cfg, dict) and "threshold" in cfg:
                thresholds[key] = float(cfg["threshold"])
        return thresholds
    except Exception as e:
        logger.error(f"加载置信度配置文件失败: {e}")
        return {}


def clear_calculator_cache() -> None:
    """清空计算器缓存，用于配置热加载"""
    _calculator_registry.clear()
    logger.info("置信度计算器缓存已清空")


# ---------------------------------------------------------------------------
# requires_confidence 装饰器
# ---------------------------------------------------------------------------


def requires_confidence(
    threshold: float = 0.90,
    industry: str | None = None,
    variance_key: str = "variance",
    config_path: str | Path | None = None,
) -> Callable:
    """置信度门控装饰器

    在函数执行前检查输入数据的置信度是否达到阈值。
    低于阈值时抛出 ConfidenceInsufficientError。

    Usage:
        @requires_confidence(threshold=0.90, industry="topography")
        def generate_topography_recommendations(variance_grid, **kwargs):
            ...

    Args:
        threshold: 最低置信度阈值
        industry: 行业类型 (用于选择计算器)，None 则从配置推断
        variance_key: 从 kwargs 中提取方差数据的键名
        config_path: 配置文件路径
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 提取方差数据
            variance = kwargs.get(variance_key)
            if variance is None and args:
                # 尝试从第一个参数获取
                variance = args[0] if not isinstance(args[0], (object,)) or hasattr(args[0], "variance") else None
                if hasattr(args[0], "variance"):
                    variance = getattr(args[0], "variance")

            if variance is None:
                logger.warning(f"装饰器 @requires_confidence 无法提取方差数据 (key='{variance_key}')，跳过检查")
                return func(*args, **kwargs)

            # 确定行业类型
            effective_industry = industry or kwargs.get("industry", "unknown")

            # 构建传给计算器的额外参数（排除方差本身）
            calc_kwargs = {k: v for k, v in kwargs.items() if k != variance_key}

            # 获取计算器并检查
            calc = get_confidence_calculator(effective_industry, config_path=config_path)
            result = calc.check(variance, **calc_kwargs)

            logger.info(
                f"置信度门控通过: industry={effective_industry}, "
                f"score={result.score:.3f} >= threshold={result.threshold:.2f}"
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def compute_confidence_score(
    variance: Any,
    industry: str = "unknown",
    **kwargs: Any,
) -> ConfidenceResult:
    """便捷函数: 计算置信度分数

    Args:
        variance: 方差数据 (ndarray 或 list)
        industry: 行业类型
        **kwargs: 传递给计算器的额外参数 (如 predictions, r2_score, anomaly_score)

    Returns:
        ConfidenceResult 包含 score, threshold, is_sufficient 等
    """
    calc = get_confidence_calculator(industry)
    return calc.calculate(variance, **kwargs)
