"""System integration adapter for stage-6 spatiotemporal forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

import numpy as np

from deep_learning.utils.cache import CacheManager

from .analysis_tools import (
    acf,
    adf_proxy_test,
    cross_correlation,
    detect_spatiotemporal_anomalies,
    detect_temporal_anomalies,
    fft_spectrum,
    kpss_proxy_test,
    pacf,
    seasonal_decompose,
)
from .evaluation import (
    ablation_study,
    benchmark_comparison,
    evaluate_spatial_dimension,
    evaluate_spatiotemporal_metrics,
    evaluate_time_dimension,
    generate_report,
)
from .graph import build_knn_graph
from .models import ConvLSTMModel, GCNLSTMModel, STGCNModel, SpatioTemporalOutput, SpatioTemporalTransformer
from .online import OnlineModelUpdater, OnlineSpatioTemporalPredictor
from .training import SpatioTemporalTrainingConfig, train_spatiotemporal_model

ModelType = Literal["st_transformer", "gcn_lstm", "convlstm", "stgcn"]


@dataclass
class IntegratedSpatioTemporalResult:
    mean: np.ndarray
    variance: np.ndarray
    model_type: str
    source: str


class SpatioTemporalSystemIntegrator:
    """Bridge spatiotemporal models with service/API and online pipeline."""

    def __init__(self, cache_ttl_seconds: int = 180, seed: int = 42) -> None:
        self.seed = seed
        self.cache = CacheManager(ttl_seconds=cache_ttl_seconds)
        self.models: dict[str, Any] = {}
        self.training_records: dict[str, dict[str, Any]] = {}
        self.online_predictor = OnlineSpatioTemporalPredictor()
        self.online_updater = OnlineModelUpdater()

    def _build_model(self, model_type: ModelType, pred_horizon: int) -> Any:
        if model_type == "st_transformer":
            return SpatioTemporalTransformer(dim=32, num_heads=4, pred_horizon=pred_horizon, seed=self.seed)
        if model_type == "gcn_lstm":
            return GCNLSTMModel(dim=28, layers=2, bidirectional=True, pred_horizon=pred_horizon, seed=self.seed)
        if model_type == "convlstm":
            return ConvLSTMModel(dim=24, pred_horizon=pred_horizon, seed=self.seed)
        return STGCNModel(dim=24, n_blocks=3, pred_horizon=pred_horizon, seed=self.seed)

    def _get_model(self, model_type: ModelType, pred_horizon: int) -> Any:
        key = f"{model_type}:{int(pred_horizon)}"
        if key not in self.models:
            self.models[key] = self._build_model(model_type=model_type, pred_horizon=int(pred_horizon))
        return self.models[key]

    def _validate(self, coords: np.ndarray, series: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(series, dtype=float)
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [n_nodes, 2]")
        if s.ndim != 3:
            raise ValueError("series must be [n_nodes, seq_len, n_features]")
        if s.shape[0] != c.shape[0]:
            raise ValueError("coords and series node count mismatch")
        return c, s

    def train(
        self,
        model_type: ModelType,
        train_dataset: list[dict[str, np.ndarray]],
        val_dataset: list[dict[str, np.ndarray]],
        config: SpatioTemporalTrainingConfig | None = None,
    ) -> dict[str, Any]:
        cfg = config or SpatioTemporalTrainingConfig()
        model = self._get_model(model_type=model_type, pred_horizon=cfg.pred_horizon)
        result = train_spatiotemporal_model(model, train_dataset=train_dataset, val_dataset=val_dataset, config=cfg)
        self.training_records[model_type] = result
        return result

    def predict(
        self,
        model_type: ModelType,
        coords: np.ndarray,
        series: np.ndarray,
        pred_horizon: int = 6,
        fusion_strategy: str = "gating",
        legacy_prediction: np.ndarray | None = None,
        blend_ratio: float = 0.7,
    ) -> IntegratedSpatioTemporalResult:
        c, s = self._validate(coords, series)
        model = self._get_model(model_type=model_type, pred_horizon=pred_horizon)

        cache_key = f"st:{model_type}:{pred_horizon}:{hash(c.tobytes())}:{hash(s.tobytes())}:{fusion_strategy}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if model_type == "st_transformer":
            out: SpatioTemporalOutput = model.forward(c, s, fusion_strategy=fusion_strategy)
        else:
            out = model.forward(c, s)

        mean = out.mean
        var = out.variance
        source = model_type

        if legacy_prediction is not None:
            legacy = np.asarray(legacy_prediction, dtype=float)
            if legacy.shape == mean.shape:
                r = float(np.clip(blend_ratio, 0.0, 1.0))
                mean = r * mean + (1.0 - r) * legacy
                source = f"{model_type}+legacy"

        result = IntegratedSpatioTemporalResult(mean=mean, variance=np.maximum(var, 1e-6), model_type=model_type, source=source)
        self.cache.set(cache_key, result)
        return result

    def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_var: np.ndarray,
        coords: np.ndarray,
        baseline_preds: dict[str, np.ndarray] | None = None,
        ablation_scores: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        metrics = evaluate_spatiotemporal_metrics(y_true, y_pred, y_var)
        t_eval = evaluate_time_dimension(y_true, y_pred)
        s_eval = evaluate_spatial_dimension(y_true, y_pred, coords)

        baselines = baseline_preds or {}
        benchmark = benchmark_comparison(y_true, y_pred, baselines)
        ablation = ablation_study(full_score=metrics.rmse, variants=ablation_scores or {})
        report = generate_report(metrics=metrics, time_eval=t_eval, spatial_eval=s_eval, benchmark=benchmark, ablation=ablation)

        return {
            "metrics": metrics.__dict__,
            "time": t_eval,
            "spatial": s_eval,
            "benchmark": benchmark,
            "ablation": ablation,
            "report": report,
        }

    def baseline_predictions(self, series: np.ndarray, pred_horizon: int = 6) -> dict[str, np.ndarray]:
        s = np.asarray(series, dtype=float)
        target_series = s[:, :, 0]

        # Naive: repeat last value.
        last = target_series[:, -1:]
        naive = np.repeat(last, pred_horizon, axis=1)

        # ARIMA-like proxy: linear trend extrapolation.
        t = np.arange(target_series.shape[1], dtype=float)
        trend_pred = np.zeros((target_series.shape[0], pred_horizon), dtype=float)
        for i in range(target_series.shape[0]):
            coeff = np.polyfit(t, target_series[i], deg=1)
            future_t = np.arange(target_series.shape[1], target_series.shape[1] + pred_horizon, dtype=float)
            trend_pred[i] = coeff[0] * future_t + coeff[1]

        # LSTM-like proxy: exponential smoothing recurrence.
        alpha = 0.7
        smooth = np.zeros(target_series.shape[0], dtype=float)
        for i in range(target_series.shape[1]):
            smooth = alpha * target_series[:, i] + (1.0 - alpha) * smooth
        lstm_like = np.repeat(smooth[:, None], pred_horizon, axis=1)

        return {
            "arima_proxy": trend_pred,
            "lstm_proxy": lstm_like,
            "naive": naive,
        }

    def analyze_time_series(self, series: np.ndarray, adjacency: np.ndarray | None = None) -> dict[str, Any]:
        s = np.asarray(series, dtype=float)
        target = s[:, :, 0] if s.ndim == 3 else s
        avg_series = np.mean(target, axis=0)

        out: dict[str, Any] = {
            "decomposition": seasonal_decompose(avg_series, period=max(4, len(avg_series) // 4)),
            "adf": adf_proxy_test(avg_series),
            "kpss": kpss_proxy_test(avg_series),
            "acf": acf(avg_series, max_lag=min(20, len(avg_series) - 2)),
            "pacf": pacf(avg_series, max_lag=min(10, len(avg_series) - 2)),
            "fft": fft_spectrum(avg_series),
            "temporal_anomaly": detect_temporal_anomalies(avg_series),
        }

        if target.shape[0] >= 2:
            out["cross_correlation"] = cross_correlation(target[0], target[1], max_lag=min(8, len(avg_series) // 2))

        if adjacency is not None:
            out["spatiotemporal_anomaly"] = detect_spatiotemporal_anomalies(target, adjacency)

        return out

    def realtime_predict_and_update(
        self,
        model_type: ModelType,
        coords: np.ndarray,
        long_series: np.ndarray,
        window_size: int = 24,
        pred_horizon: int = 6,
        update_interval: int = 1,
        strategy: str = "standard",
    ) -> dict[str, Any]:
        c, s = self._validate(coords, long_series)
        model = self._get_model(model_type=model_type, pred_horizon=pred_horizon)

        sliding = self.online_predictor.sliding_window_predict(
            model=model,
            coords=c,
            long_series=s,
            window_size=window_size,
            pred_horizon=pred_horizon,
            step_size=1,
        )

        stream_batches: list[dict[str, np.ndarray]] = []
        for item in sliding["windows"]:
            start = int(item["start"])
            stream_batches.append(
                {
                    "coords": c,
                    "series": s[:, start : start + window_size, :],
                    "targets": s[:, start + window_size : start + window_size + pred_horizon, 0],
                    "adjacency": build_knn_graph(c, k=min(6, max(1, len(c) - 1))).adjacency,
                }
            )

        online = self.online_updater.online_learning(
            model=model,
            stream_batches=stream_batches,
            update_interval=update_interval,
            lr=0.01,
        )
        tune = self.online_updater.fine_tune(model=model, recent_data=stream_batches[-3:] or stream_batches, strategy=strategy)

        return {
            "sliding_count": int(sliding["count"]),
            "online_update": online.__dict__,
            "fine_tune": tune.__dict__,
        }

    def performance_benchmark(
        self,
        model_type: ModelType,
        coords: np.ndarray,
        series: np.ndarray,
        pred_horizon: int = 6,
        repeat: int = 5,
    ) -> dict[str, float]:
        model = self._get_model(model_type=model_type, pred_horizon=pred_horizon)
        c, s = self._validate(coords, series)

        times: list[float] = []
        for _ in range(max(1, repeat)):
            st = perf_counter()
            _ = model.forward(c, s)
            times.append((perf_counter() - st) * 1000.0)

        avg = float(np.mean(times))
        return {
            "latency_ms": avg,
            "throughput_samples_per_sec": float((len(c) * max(1, pred_horizon)) / max(avg / 1000.0, 1e-8)),
            "repeat": float(max(1, repeat)),
        }

    def api_predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_type = str(payload.get("model_type", "st_transformer"))
        if model_type not in {"st_transformer", "gcn_lstm", "convlstm", "stgcn"}:
            raise ValueError("model_type must be one of st_transformer/gcn_lstm/convlstm/stgcn")

        coords = np.asarray(payload["coords"], dtype=float)
        series = np.asarray(payload["series"], dtype=float)
        pred_horizon = int(payload.get("pred_horizon", 6))
        fusion_strategy = str(payload.get("fusion_strategy", "gating"))

        pred = self.predict(
            model_type=model_type,  # type: ignore[arg-type]
            coords=coords,
            series=series,
            pred_horizon=pred_horizon,
            fusion_strategy=fusion_strategy,
            legacy_prediction=np.asarray(payload.get("legacy_prediction"), dtype=float)
            if payload.get("legacy_prediction") is not None
            else None,
            blend_ratio=float(payload.get("blend_ratio", 0.7)),
        )

        baselines = self.baseline_predictions(series=series, pred_horizon=pred_horizon)
        target = np.asarray(payload.get("targets"), dtype=float) if payload.get("targets") is not None else None

        if target is not None and target.shape == pred.mean.shape:
            eval_payload = self.evaluate(target, pred.mean, pred.variance, coords=coords, baseline_preds=baselines)
        else:
            eval_payload = {
                "metrics": None,
                "time": None,
                "spatial": None,
                "benchmark": None,
                "ablation": None,
                "report": None,
            }

        analysis = self.analyze_time_series(series)
        perf = self.performance_benchmark(model_type=model_type, coords=coords, series=series, pred_horizon=pred_horizon, repeat=3)  # type: ignore[arg-type]

        return {
            "prediction": pred.mean.tolist(),
            "variance": pred.variance.tolist(),
            "model_type": pred.model_type,
            "source": pred.source,
            "evaluation": eval_payload,
            "analysis": {
                "adf": analysis["adf"],
                "kpss": analysis["kpss"],
                "temporal_anomaly_count": int(len(analysis["temporal_anomaly"]["indices"])),
            },
            "performance": perf,
        }
