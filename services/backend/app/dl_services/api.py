"""深度学习服务 API。"""

from __future__ import annotations

from typing import Optional

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


class SpatioTemporalTrainRequest(BaseModel):
    model_type: str = Field(default="st_transformer", description="st_transformer/gcn_lstm/convlstm/stgcn")
    coords: list[list[float]] = Field(default_factory=list, description="[[x, y], ...]")
    series: list[list[list[float]]] = Field(default_factory=list, description="[n_nodes, seq_len, n_features]")
    targets: Optional[list[list[float]]] = Field(default=None, description="[n_nodes, pred_horizon], 可选")
    epochs: int = Field(default=20, ge=5, le=300)
    pred_horizon: int = Field(default=6, ge=1, le=48)


class SpatioTemporalPredictRequest(BaseModel):
    model_type: str = Field(default="st_transformer", description="st_transformer/gcn_lstm/convlstm/stgcn")
    coords: list[list[float]] = Field(default_factory=list, description="[[x, y], ...]")
    series: list[list[list[float]]] = Field(default_factory=list, description="[n_nodes, seq_len, n_features]")
    pred_horizon: int = Field(default=6, ge=1, le=48)
    fusion_strategy: str = Field(default="gating", description="concat/add/gating")
    targets: Optional[list[list[float]]] = Field(default=None, description="[n_nodes, pred_horizon], 可选")
    blend_ratio: float = Field(default=0.7, ge=0.0, le=1.0)
    uncertainty_method: Optional[str] = Field(default=None, description="mc_dropout/deep_ensemble/bayesian")
    enable_memory_optimization: bool = Field(default=False)
    enable_gpu_acceleration: bool = Field(default=False)
    enable_inference_acceleration: bool = Field(default=True)
    enable_long_sequence_optimization: bool = Field(default=False)
    long_sequence_chunk: int = Field(default=48, ge=8, le=512)


class SpatioTemporalOnlineRequest(BaseModel):
    model_type: str = Field(default="st_transformer", description="st_transformer/gcn_lstm/convlstm/stgcn")
    coords: list[list[float]] = Field(default_factory=list, description="[[x, y], ...]")
    long_series: list[list[list[float]]] = Field(default_factory=list, description="[n_nodes, total_steps, n_features]")
    window_size: int = Field(default=24, ge=4, le=256)
    pred_horizon: int = Field(default=6, ge=1, le=48)
    update_interval: int = Field(default=1, ge=1, le=20)
    strategy: str = Field(default="standard", description="light/standard/aggressive")


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


@router.post("/spatiotemporal/train")
def train_spatiotemporal(payload: SpatioTemporalTrainRequest) -> dict:
    return service.train_spatiotemporal_model(
        model_type=payload.model_type,
        coords=payload.coords,
        series=payload.series,
        targets=payload.targets,
        epochs=payload.epochs,
        pred_horizon=payload.pred_horizon,
    )


@router.post("/spatiotemporal/predict")
def predict_spatiotemporal(payload: SpatioTemporalPredictRequest) -> dict:
    return service.predict_spatiotemporal(
        model_type=payload.model_type,
        coords=payload.coords,
        series=payload.series,
        pred_horizon=payload.pred_horizon,
        fusion_strategy=payload.fusion_strategy,
        targets=payload.targets,
        blend_ratio=payload.blend_ratio,
        uncertainty_method=payload.uncertainty_method,
        enable_memory_optimization=payload.enable_memory_optimization,
        enable_gpu_acceleration=payload.enable_gpu_acceleration,
        enable_inference_acceleration=payload.enable_inference_acceleration,
        enable_long_sequence_optimization=payload.enable_long_sequence_optimization,
        long_sequence_chunk=payload.long_sequence_chunk,
    )


@router.post("/spatiotemporal/online-update")
def update_spatiotemporal_online(payload: SpatioTemporalOnlineRequest) -> dict:
    return service.update_spatiotemporal_online(
        model_type=payload.model_type,
        coords=payload.coords,
        long_series=payload.long_series,
        window_size=payload.window_size,
        pred_horizon=payload.pred_horizon,
        update_interval=payload.update_interval,
        strategy=payload.strategy,
    )
