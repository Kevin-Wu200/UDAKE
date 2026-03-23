"""深度学习服务 API。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .service import DeepLearningService

router = APIRouter(prefix="/dl", tags=["深度学习"])
service = DeepLearningService()


class TrainRequest(BaseModel):
    samples: list[list[float]] = Field(default_factory=list, description="每条样本最后一列为监督目标")


class PredictRequest(BaseModel):
    samples: list[list[float]] = Field(default_factory=list)
    bias: float = Field(default=0.0, description="示例模型偏置项")


@router.get("/health")
def dl_health() -> dict:
    return service.health()


@router.post("/train-demo")
def train_demo(payload: TrainRequest) -> dict:
    return service.train_demo_model(payload.samples)


@router.post("/predict")
def predict(payload: PredictRequest) -> dict:
    return service.predict(payload.samples, bias=payload.bias)
