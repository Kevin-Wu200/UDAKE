"""时空克里金请求/响应 Schema。"""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class STSeriesSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    x: List[float] = Field(default_factory=list)
    y: List[float] = Field(default_factory=list)
    z: List[float] = Field(default_factory=list)
    t: List[float] = Field(default_factory=list)
    value: List[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lengths(self) -> "STSeriesSchema":
        n = len(self.x)
        if n < 3:
            raise ValueError("至少需要 3 个样本点")
        if not (len(self.y) == n and len(self.z) == n and len(self.t) == n and len(self.value) == n):
            raise ValueError("x/y/z/t/value 长度必须一致")
        return self


class STTrainRequestSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    data: STSeriesSchema
    model_type: Literal["separated", "product", "nonseparable"] = "separated"
    options: Dict[str, Any] = Field(default_factory=dict)


class STPredictRequestSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    target_positions: Dict[str, List[float]]
    target_times: List[float] = Field(default_factory=list)
    prediction_days: int = Field(default=1, ge=1, le=15)
    options: Dict[str, Any] = Field(default_factory=dict)
