"""API 端点扩展通用模型。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExplainModelType(str, Enum):
    """解释服务支持的模型类型枚举。"""

    ANOMALY = "anomaly"
    INTERPOLATION = "interpolation"
    UNCERTAINTY = "uncertainty"
    FUSION = "fusion"
    RL = "rl"


_SUPPORTED_MODEL_TYPES = tuple(item.value for item in ExplainModelType)


def _coerce_int(value: Any, *, field_name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 不能为布尔值")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{field_name} 必须是整数")
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("+"):
        text = text[1:]
    if not text.isdigit():
        raise ValueError(f"{field_name} 必须是整数")
    return int(text)


class GenericModelExplainRequest(BaseModel):
    """统一模型解释端点请求结构。"""

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    model_type: ExplainModelType = Field(description="模型类别：anomaly/interpolation/uncertainty/fusion/rl")
    model_name: Optional[str] = Field(default=None, description="具体模型名，缺省时按模型类别使用默认值")
    method: str = Field(default="hybrid", description="解释方法：lime/shap/hybrid")
    top_k: int = Field(default=5, ge=1, le=20, description="返回特征重要性 Top-K")
    include_prediction: bool = Field(default=True, description="是否包含预测结果")
    sample_count: Optional[int] = Field(default=None, ge=1, le=200000, description="样本数量")
    feature_selection: Optional[list[int]] = Field(default=None, description="特征索引列表")
    max_explain_nodes: int = Field(default=8, ge=1, le=128, description="最大解释节点数")
    num_samples: Optional[int] = Field(default=None, ge=80, le=2000, description="LIME 采样数")
    nsamples: Optional[int] = Field(default=None, ge=40, le=2000, description="SHAP 采样数")
    payload: dict[str, Any] = Field(default_factory=dict, description="模型类型对应的请求体")

    @field_validator("model_type", mode="before")
    @classmethod
    def validate_model_type(cls, value: Any) -> ExplainModelType:
        text = str(value or "").strip().lower()
        try:
            return ExplainModelType(text)
        except ValueError as exc:
            raise ValueError(
                f"无效模型类型: {value}，支持类型: {', '.join(_SUPPORTED_MODEL_TYPES)}"
            ) from exc

    @field_validator("top_k", "sample_count", "max_explain_nodes", "num_samples", "nsamples", mode="before")
    @classmethod
    def coerce_numeric_int(cls, value: Any, info) -> Optional[int]:
        return _coerce_int(value, field_name=info.field_name)

    @field_validator("feature_selection", mode="before")
    @classmethod
    def coerce_feature_selection(cls, value: Any) -> Optional[list[int]]:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            value = [item.strip() for item in text.split(",")]
        if not isinstance(value, list):
            raise ValueError("feature_selection 必须是整数列表或逗号分隔字符串")
        result: list[int] = []
        for item in value:
            converted = _coerce_int(item, field_name="feature_selection item")
            if converted is None:
                continue
            result.append(converted)
        return result or None

    @model_validator(mode="after")
    def fill_defaults_and_check_ranges(self) -> "GenericModelExplainRequest":
        if self.sample_count is None:
            for key in ("samples", "coords", "features", "models", "uncertainty_map"):
                raw = self.payload.get(key)
                if isinstance(raw, list):
                    self.sample_count = len(raw)
                    break
        if self.sample_count is not None and not (1 <= self.sample_count <= 200000):
            raise ValueError("sample_count 超出范围，必须在 1-200000 之间")
        if self.feature_selection is not None and len(self.feature_selection) > 256:
            raise ValueError("feature_selection 数量过多，最多支持 256 个特征")
        return self

