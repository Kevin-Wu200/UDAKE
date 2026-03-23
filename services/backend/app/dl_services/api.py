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


class SpatialTrainRequest(BaseModel):
    model_type: str = Field(default="gnn", description="gnn/attention/residual")
    samples: list[list[float]] = Field(default_factory=list, description="[[x, y, value], ...]")
    epochs: int = Field(default=30, ge=1, le=200)


class SpatialPredictRequest(BaseModel):
    model_type: str = Field(default="gnn", description="gnn/attention/residual")
    samples: list[list[float]] = Field(default_factory=list, description="[[x, y, value], ...]")
    queries: list[list[float]] = Field(default_factory=list, description="[[x, y], ...]")
    blend_ratio: float = Field(default=0.6, ge=0.0, le=1.0)


class AnomalyTrainRequest(BaseModel):
    model_name: str = Field(default="vae", description="vae/gcae/gan/contrastive")
    coords: list[list[float]] = Field(default_factory=list, description="[[x, y], ...]")
    values: list[float] = Field(default_factory=list, description="[value, ...]")
    epochs: int = Field(default=30, ge=1, le=300)


class AnomalyPredictRequest(BaseModel):
    model_name: str = Field(default="vae", description="vae/gcae/gan/contrastive/fusion")
    coords: list[list[float]] = Field(default_factory=list, description="[[x, y], ...]")
    values: list[float] = Field(default_factory=list, description="[value, ...]")
    threshold_method: str = Field(default="percentile", description="statistical/percentile/adaptive")
    percentile: float = Field(default=95.0, ge=50.0, le=99.9)
    k: float = Field(default=2.5, ge=1.0, le=6.0)


class RealtimeBatch(BaseModel):
    coords: list[list[float]] = Field(default_factory=list, description="[[x, y], ...]")
    values: list[float] = Field(default_factory=list, description="[value, ...]")


class AnomalyRealtimeRequest(BaseModel):
    model_name: str = Field(default="vae", description="vae/gcae/gan/contrastive/fusion")
    stream_batches: list[RealtimeBatch] = Field(default_factory=list)
    threshold_method: str = Field(default="adaptive", description="statistical/percentile/adaptive")
    percentile: float = Field(default=95.0, ge=50.0, le=99.9)
    k: float = Field(default=2.5, ge=1.0, le=6.0)


class SamplingRLTrainRequest(BaseModel):
    model_name: str = Field(default="ppo", description="ppo/dqn/a2c/a3c")
    uncertainty_map: list[list[float]] = Field(default_factory=list, description="二维不确定性矩阵")
    existing_points: list[list[float]] = Field(default_factory=list, description="已有采样点 [[x, y], ...]")
    episodes: int = Field(default=30, ge=5, le=500)
    budget: int = Field(default=20, ge=8, le=200)


class SamplingRLPredictRequest(BaseModel):
    model_name: str = Field(default="ppo", description="ppo/dqn/a2c/a3c")
    uncertainty_map: list[list[float]] = Field(default_factory=list, description="二维不确定性矩阵")
    existing_points: list[list[float]] = Field(default_factory=list, description="已有采样点 [[x, y], ...]")
    n_recommendations: int = Field(default=10, ge=1, le=100)
    fusion_strategy: str = Field(default="hybrid", description="rl_only/rule_only/hybrid")
    realtime: bool = Field(default=True, description="是否使用实时推荐模式")


@router.get("/health")
def dl_health() -> dict:
    return service.health()


@router.post("/train-demo")
def train_demo(payload: TrainRequest) -> dict:
    return service.train_demo_model(payload.samples)


@router.post("/predict")
def predict(payload: PredictRequest) -> dict:
    return service.predict(payload.samples, bias=payload.bias)


@router.post("/spatial/train")
def train_spatial(payload: SpatialTrainRequest) -> dict:
    return service.train_spatial_model(model_type=payload.model_type, samples=payload.samples, epochs=payload.epochs)


@router.post("/spatial/predict")
def predict_spatial(payload: SpatialPredictRequest) -> dict:
    return service.predict_spatial(
        model_type=payload.model_type,
        samples=payload.samples,
        queries=payload.queries,
        blend_ratio=payload.blend_ratio,
    )


@router.post("/anomaly/train")
def train_anomaly(payload: AnomalyTrainRequest) -> dict:
    return service.train_anomaly_model(
        model_name=payload.model_name,
        coords=payload.coords,
        values=payload.values,
        epochs=payload.epochs,
    )


@router.post("/anomaly/predict")
def predict_anomaly(payload: AnomalyPredictRequest) -> dict:
    return service.predict_anomaly(
        model_name=payload.model_name,
        coords=payload.coords,
        values=payload.values,
        threshold_method=payload.threshold_method,
        percentile=payload.percentile,
        k=payload.k,
    )


@router.post("/anomaly/realtime")
def anomaly_realtime(payload: AnomalyRealtimeRequest) -> dict:
    return service.detect_realtime_anomaly(
        model_name=payload.model_name,
        stream_batches=[item.model_dump() for item in payload.stream_batches],
        threshold_method=payload.threshold_method,
        percentile=payload.percentile,
        k=payload.k,
    )


@router.post("/sampling-rl/train")
def train_sampling_rl(payload: SamplingRLTrainRequest) -> dict:
    return service.train_sampling_rl(
        model_name=payload.model_name,
        uncertainty_map=payload.uncertainty_map,
        existing_points=payload.existing_points,
        episodes=payload.episodes,
        budget=payload.budget,
    )


@router.post("/sampling-rl/recommend")
def recommend_sampling_rl(payload: SamplingRLPredictRequest) -> dict:
    return service.recommend_sampling_rl(
        model_name=payload.model_name,
        uncertainty_map=payload.uncertainty_map,
        existing_points=payload.existing_points,
        n_recommendations=payload.n_recommendations,
        fusion_strategy=payload.fusion_strategy,
        realtime=payload.realtime,
    )
