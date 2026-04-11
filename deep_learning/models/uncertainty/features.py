"""不确定性量化模型特征分析与统一提取。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

ModelType = Literal["bnn", "mc_dropout", "deep_ensemble", "edl"]


@dataclass(frozen=True)
class UncertaintyFeatureSpec:
    model_type: ModelType
    feature_keys: tuple[str, ...]
    uncertainty_keys: tuple[str, ...]
    extraction_plan: tuple[str, ...]
    decomposition_strategy: str


BNN_FEATURE_KEYS = (
    "mean",
    "variance",
    "aleatoric",
    "epistemic",
    "lower",
    "upper",
    "confidence",
    "num_samples",
)

MC_DROPOUT_FEATURE_KEYS = (
    "mean",
    "variance",
    "aleatoric",
    "epistemic",
    "lower",
    "upper",
    "confidence",
    "t",
)

DEEP_ENSEMBLE_FEATURE_KEYS = (
    "mean",
    "variance",
    "aleatoric",
    "epistemic",
    "lower",
    "upper",
    "quantiles.q10",
    "quantiles.q50",
    "quantiles.q90",
    "member_count",
    "aggregation",
)

EDL_FEATURE_KEYS = (
    "logits",
    "evidence",
    "alpha",
    "probabilities",
    "prediction",
    "confidence",
    "uncertainty.total",
    "uncertainty.data",
    "uncertainty.knowledge",
    "uncertainty.threshold",
)

_MODEL_FEATURE_REGISTRY: dict[ModelType, UncertaintyFeatureSpec] = {
    "bnn": UncertaintyFeatureSpec(
        model_type="bnn",
        feature_keys=BNN_FEATURE_KEYS,
        uncertainty_keys=("aleatoric", "epistemic", "variance"),
        extraction_plan=(
            "标准化字段结构（标量/数组）",
            "提取均值与置信区间",
            "提取总/认知/偶然不确定性",
            "输出可解释性映射键",
        ),
        decomposition_strategy="直接使用采样分解结果：epistemic/aleatoric",
    ),
    "mc_dropout": UncertaintyFeatureSpec(
        model_type="mc_dropout",
        feature_keys=MC_DROPOUT_FEATURE_KEYS,
        uncertainty_keys=("aleatoric", "epistemic", "variance"),
        extraction_plan=(
            "读取多次随机前向统计量",
            "提取 t 次采样稳定后的均值/方差",
            "按字段输出认知/偶然不确定性",
            "保留采样步数用于解释对比",
        ),
        decomposition_strategy="直接使用蒙特卡洛采样分解结果：epistemic/aleatoric",
    ),
    "deep_ensemble": UncertaintyFeatureSpec(
        model_type="deep_ensemble",
        feature_keys=DEEP_ENSEMBLE_FEATURE_KEYS,
        uncertainty_keys=("aleatoric", "epistemic", "variance"),
        extraction_plan=(
            "聚合成员预测结果",
            "提取分位数与区间信息",
            "提取总/认知/偶然不确定性",
            "输出成员数量与聚合方式",
        ),
        decomposition_strategy="成员方差对应认知不确定性，成员内方差对应偶然不确定性",
    ),
    "edl": UncertaintyFeatureSpec(
        model_type="edl",
        feature_keys=EDL_FEATURE_KEYS,
        uncertainty_keys=("uncertainty.knowledge", "uncertainty.data", "uncertainty.total"),
        extraction_plan=(
            "读取证据与Dirichlet参数",
            "从 uncertainty 子结构提取 knowledge/data",
            "将 knowledge 映射为认知不确定性",
            "将 data 映射为偶然不确定性并计算占比",
        ),
        decomposition_strategy="knowledge->epistemic，data->aleatoric",
    ),
}

_FEATURE_NAME_MAPPING: dict[str, str] = {
    "mean": "预测均值",
    "variance": "总预测方差",
    "aleatoric": "偶然不确定性",
    "epistemic": "认知不确定性",
    "lower": "置信区间下界",
    "upper": "置信区间上界",
    "confidence": "置信度",
    "num_samples": "采样次数",
    "t": "蒙特卡洛采样次数",
    "quantiles.q10": "10分位预测",
    "quantiles.q50": "50分位预测",
    "quantiles.q90": "90分位预测",
    "member_count": "集成成员数量",
    "aggregation": "集成聚合方式",
    "logits": "分类logits",
    "evidence": "证据强度",
    "alpha": "Dirichlet参数",
    "probabilities": "类别概率",
    "prediction": "预测类别",
    "uncertainty.total": "总不确定性",
    "uncertainty.data": "数据不确定性",
    "uncertainty.knowledge": "知识不确定性",
    "uncertainty.threshold": "不确定性阈值",
}


def uncertainty_feature_registry() -> dict[ModelType, UncertaintyFeatureSpec]:
    return dict(_MODEL_FEATURE_REGISTRY)


def feature_name_mapping() -> dict[str, str]:
    return dict(_FEATURE_NAME_MAPPING)


def model_feature_keys(model_type: ModelType) -> tuple[str, ...]:
    return _MODEL_FEATURE_REGISTRY[model_type].feature_keys


def _to_array(value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        return np.asarray([float(arr)], dtype=float)
    return arr


def _read_nested(payload: dict[str, Any], key: str) -> Any:
    if "." not in key:
        return payload.get(key)
    cur: Any = payload
    for seg in key.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return None
        cur = cur[seg]
    return cur


def extract_model_features(model_type: ModelType, prediction: dict[str, Any]) -> dict[str, Any]:
    """按模型类型提取标准化特征字典。"""

    keys = model_feature_keys(model_type)
    out: dict[str, Any] = {}
    for key in keys:
        value = _read_nested(prediction, key)
        if value is None:
            continue
        if isinstance(value, (list, np.ndarray, tuple, int, float, np.number)):
            out[key] = _to_array(value)
        else:
            out[key] = value

    # 常用别名，便于调用方统一处理。
    if "uncertainty.total" in out and "variance" not in out:
        out["variance"] = np.maximum(_to_array(out["uncertainty.total"]), 1e-8)
    if "uncertainty.data" in out and "aleatoric" not in out:
        out["aleatoric"] = np.maximum(_to_array(out["uncertainty.data"]), 0.0)
    if "uncertainty.knowledge" in out and "epistemic" not in out:
        out["epistemic"] = np.maximum(_to_array(out["uncertainty.knowledge"]), 0.0)
    if model_type == "deep_ensemble" and "member_count" not in out:
        members = prediction.get("member_ids", [])
        out["member_count"] = np.asarray([float(len(members))], dtype=float)

    return out


def decompose_uncertainty_sources(model_type: ModelType, prediction: dict[str, Any]) -> dict[str, np.ndarray | str]:
    """统一认知/偶然不确定性分解输出。"""

    features = extract_model_features(model_type, prediction)
    epistemic = np.maximum(_to_array(features.get("epistemic", 0.0)), 0.0)
    aleatoric = np.maximum(_to_array(features.get("aleatoric", 0.0)), 0.0)

    if "variance" in features:
        total = np.maximum(_to_array(features["variance"]), 1e-8)
    else:
        total = np.maximum(epistemic + aleatoric, 1e-8)

    if np.any(epistemic <= 0.0) and np.any(total > aleatoric):
        epistemic = np.maximum(total - aleatoric, 0.0)
    if np.any(aleatoric <= 0.0) and np.any(total > epistemic):
        aleatoric = np.maximum(total - epistemic, 0.0)

    denom = np.maximum(epistemic + aleatoric, 1e-8)
    epi_ratio = np.clip(epistemic / denom, 0.0, 1.0)
    ale_ratio = np.clip(aleatoric / denom, 0.0, 1.0)

    return {
        "epistemic": epistemic,
        "aleatoric": aleatoric,
        "total": total,
        "epistemic_ratio": epi_ratio,
        "aleatoric_ratio": ale_ratio,
        "strategy": _MODEL_FEATURE_REGISTRY[model_type].decomposition_strategy,
    }
