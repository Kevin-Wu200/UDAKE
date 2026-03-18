"""
融合模型定义
"""
from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any, Optional
from enum import Enum


class FusionStrategy(str, Enum):
    """融合策略枚举"""
    SIMPLE_AVERAGE = "simple_average"
    WEIGHTED_AVERAGE = "weighted_average"
    MEDIAN = "median"
    STACKING = "stacking"
    BAYESIAN_MODEL_AVERAGE = "bayesian_model_average"
    VARIANCE_WEIGHTED = "variance_weighted"
    MAX_MIN = "max_min"


class WeightMethod(str, Enum):
    """权重计算方法枚举"""
    EQUAL = "equal"
    RMSE_BASED = "rmse_based"
    MAE_BASED = "mae_based"
    R2_BASED = "r2_based"
    CROSS_VALIDATION = "cross_validation"
    BMA = "bma"
    UNCERTAINTY_BASED = "uncertainty_based"
    ADAPTIVE = "adaptive"


class ModelPrediction(BaseModel):
    """模型预测结果"""
    model_config = ConfigDict(protected_namespaces=())
    
    model_id: str
    model_name: str
    predictions: List[float]
    variances: Optional[List[float]] = None
    confidence_intervals: Optional[List[Dict[str, float]]] = None


class ModelMetrics(BaseModel):
    """模型评估指标"""
    model_config = ConfigDict(protected_namespaces=())
    
    model_id: str
    model_name: str
    rmse: float
    mae: float
    r2: float
    mape: Optional[float] = None
    stability: Optional[float] = None


class WeightConfig(BaseModel):
    """权重配置"""
    method: WeightMethod
    min_weight: float = 0.0
    max_weight: float = 1.0
    normalize: bool = True
    smoothing: bool = False
    smoothing_factor: float = 0.1


class FusionConfig(BaseModel):
    """融合配置"""
    strategy: FusionStrategy
    weight_config: WeightConfig
    enable_cross_validation: bool = True
    enable_stability_check: bool = True
    enable_uncertainty_propagation: bool = True
    n_folds: int = 5


class FusionResult(BaseModel):
    """融合结果"""
    fused_predictions: List[float]
    fused_variances: Optional[List[float]] = None
    weights: Dict[str, float]
    metrics: Dict[str, Any]
    individual_predictions: List[ModelPrediction]
    fusion_strategy: str
    weight_method: str
    improvement: Optional[Dict[str, float]] = None


class FusionTask(BaseModel):
    """融合任务"""
    task_id: str
    config: FusionConfig
    models: List[ModelPrediction]
    true_values: Optional[List[float]] = None
    status: str = "pending"
    result: Optional[FusionResult] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None