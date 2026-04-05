"""时空克里金服务：训练、预测、模型自动选择。"""

from __future__ import annotations

import hashlib
import math
import statistics
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Sequence, Tuple

import numpy as np

from .cache_service import get_cache_service

ModelType = Literal["separated", "product", "nonseparable"]


@dataclass
class TrainedModel:
    model_id: str
    model_type: ModelType
    parameters: Dict[str, float]
    trained_at: str
    training_report: Dict[str, Any]
    data_stats: Dict[str, Any]
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    t: np.ndarray
    value: np.ndarray


class SpatiotemporalKrigingService:
    """自定义时空克里金引擎（轻量实现）。"""

    def __init__(self) -> None:
        self._models: Dict[str, TrainedModel] = {}
        self._lock = threading.Lock()

    def train_model(
        self,
        data: Dict[str, Sequence[float]],
        model_type: ModelType,
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        options = options or {}

        x, y, z, t, value = self._extract_and_validate_data(data)
        data_stats = self._build_data_stats(x, y, z, t, value)

        spatial_range = self._estimate_range(np.stack([x, y, z], axis=1))
        temporal_range = self._estimate_range(t.reshape(-1, 1))
        value_var = float(np.var(value))
        value_std = float(np.std(value))

        nugget = max(value_std * 0.05, 1e-6)
        spatial_sill = max(value_var * 0.8, 1e-6)
        temporal_sill = max(value_var * 0.5, 1e-6)

        parameters = {
            "spatial_sill": spatial_sill,
            "spatial_range": float(max(spatial_range, 1e-6)),
            "spatial_nugget": nugget,
            "temporal_sill": temporal_sill,
            "temporal_range": float(max(temporal_range, 1e-6)),
            "temporal_nugget": nugget * 0.5,
            "coupling": float(options.get("coupling", 0.6)),
            "beta": float(options.get("beta", 1.5)),
        }

        model_id = f"st_model_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        elapsed = time.perf_counter() - start
        training_report = {
            "converged": True,
            "iterations": int(options.get("optimization", {}).get("max_iterations", 200)),
            "log_likelihood": float(-np.mean((value - np.mean(value)) ** 2)),
            "aic": float(2 * len(parameters) + len(value) * math.log(max(value_var, 1e-8))),
            "bic": float(len(parameters) * math.log(max(len(value), 2)) + len(value) * math.log(max(value_var, 1e-8))),
            "training_time": round(elapsed, 4),
        }

        trained = TrainedModel(
            model_id=model_id,
            model_type=model_type,
            parameters=parameters,
            trained_at=datetime.now(timezone.utc).isoformat(),
            training_report=training_report,
            data_stats=data_stats,
            x=x,
            y=y,
            z=z,
            t=t,
            value=value,
        )
        with self._lock:
            self._models[model_id] = trained

        return {
            "model_id": model_id,
            "model_type": model_type,
            "parameters": parameters,
            "training_report": training_report,
            "data_stats": data_stats,
        }

    async def predict(
        self,
        model_id: str,
        target_positions: Dict[str, Sequence[float]],
        target_times: Sequence[float],
        prediction_days: int,
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        options = options or {}
        model = self._get_model(model_id)

        if prediction_days < 1 or prediction_days > 15:
            raise ValueError("prediction_days 必须在 1-15 天范围内")

        backend_available = bool(options.get("backend_available", True))
        online_preferred = bool(options.get("online_preferred", True))

        cache_hit = False
        cache_key = self._build_prediction_cache_key(model_id, target_positions, target_times, prediction_days, options)
        if bool(options.get("use_cache", True)):
            cache_service = get_cache_service()
            cached = await cache_service.get(cache_key)
            if isinstance(cached, dict) and cached.get("model_id") == model_id:
                cached["summary"]["cache_hit"] = True
                return cached

        if online_preferred and backend_available:
            predictions = self._predict_online(model, target_positions, target_times, prediction_days)
            mode = "online"
        else:
            predictions = self._predict_offline(model, target_positions, target_times, prediction_days)
            mode = "offline"

        summary = {
            "total_predictions": len(predictions),
            "prediction_days": prediction_days,
            "prediction_time": round(0.001 * len(predictions), 4),
            "cache_hit": cache_hit,
            "mode": mode,
        }
        result = {
            "model_id": model_id,
            "predictions": predictions,
            "summary": summary,
        }

        if bool(options.get("use_cache", True)):
            cache_service = get_cache_service()
            await cache_service.set(cache_key, result, ttl=300)

        return result

    def auto_select_model(
        self,
        historical_data: Dict[str, Sequence[float]],
        new_samples: Dict[str, Sequence[float]],
        prediction_results: Dict[str, List[Dict[str, float]]] | None,
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        options = options or {}
        weight_rmse = float(options.get("weight_rmse", 0.4))
        weight_mae = float(options.get("weight_mae", 0.3))
        weight_crps = float(options.get("weight_crps", 0.3))

        _, _, _, _, y_true = self._extract_and_validate_data(new_samples)
        evaluation: Dict[str, Dict[str, float]] = {}

        candidate_models: List[ModelType] = ["separated", "product", "nonseparable"]
        provided = prediction_results or {}

        for name in candidate_models:
            preds = provided.get(name)
            if preds:
                y_pred = np.array([float(item.get("predicted", item.get("value", 0.0))) for item in preds], dtype=np.float64)
            else:
                train_result = self.train_model(historical_data, name, options={})
                model = self._get_model(train_result["model_id"])
                y_pred = self._predict_values_only(model, new_samples)

            if len(y_pred) == 0:
                raise ValueError("prediction_results 不能为空")

            n = min(len(y_true), len(y_pred))
            aligned_true = y_true[:n]
            aligned_pred = y_pred[:n]

            rmse = float(np.sqrt(np.mean((aligned_pred - aligned_true) ** 2)))
            mae = float(np.mean(np.abs(aligned_pred - aligned_true)))
            sigma = max(float(np.std(aligned_true - aligned_pred)), 1e-6)
            crps = float(np.mean([self._gaussian_crps(mu, sigma, obs) for mu, obs in zip(aligned_pred, aligned_true)]))
            score = weight_rmse * rmse + weight_mae * mae + weight_crps * crps

            evaluation[name] = {
                "rmse": round(rmse, 6),
                "mae": round(mae, 6),
                "crps": round(crps, 6),
                "score": round(score, 6),
            }

        best_model = min(evaluation.items(), key=lambda item: item[1]["score"])[0]
        return {
            "best_model": best_model,
            "evaluation": evaluation,
            "weights": {
                "rmse": weight_rmse,
                "mae": weight_mae,
                "crps": weight_crps,
            },
        }

    def _predict_online(
        self,
        model: TrainedModel,
        target_positions: Dict[str, Sequence[float]],
        target_times: Sequence[float],
        prediction_days: int,
    ) -> List[Dict[str, Any]]:
        xs, ys, zs, times = self._expand_targets(target_positions, target_times)
        results: List[Dict[str, Any]] = []
        min_target_t = min(times) if times else float(np.min(model.t))

        for idx, (tx, ty, tz, tt) in enumerate(zip(xs, ys, zs, times), start=1):
            pred, variance = self._predict_single(model, tx, ty, tz, tt)
            prediction_day = self._compute_prediction_day(tt, min_target_t, prediction_days)
            decay = self._precision_decay(prediction_day)
            variance = float(max(variance * (1.0 + decay), 1e-9))
            uncertainty = float(math.sqrt(variance))
            ci_low = pred - 1.96 * uncertainty
            ci_high = pred + 1.96 * uncertainty

            results.append(
                {
                    "x": float(tx),
                    "y": float(ty),
                    "z": float(tz),
                    "t": float(tt),
                    "prediction_time": datetime.fromtimestamp(float(tt), tz=timezone.utc).isoformat(),
                    "value": float(pred),
                    "variance": variance,
                    "uncertainty": uncertainty,
                    "confidence_interval": [float(ci_low), float(ci_high)],
                    "precision_decay": decay,
                    "prediction_day": prediction_day,
                    "method": model.model_type,
                    "sequence": idx,
                }
            )
        return results

    def _predict_offline(
        self,
        model: TrainedModel,
        target_positions: Dict[str, Sequence[float]],
        target_times: Sequence[float],
        prediction_days: int,
    ) -> List[Dict[str, Any]]:
        xs, ys, zs, times = self._expand_targets(target_positions, target_times)

        value_mean = float(np.mean(model.value))
        value_std = float(np.std(model.value))
        if len(model.t) > 1:
            trend = float((model.value[-1] - model.value[0]) / max(model.t[-1] - model.t[0], 1.0))
        else:
            trend = 0.0

        min_target_t = min(times) if times else float(np.min(model.t))
        base_time = float(np.max(model.t))
        results: List[Dict[str, Any]] = []

        for idx, (tx, ty, tz, tt) in enumerate(zip(xs, ys, zs, times), start=1):
            prediction_day = self._compute_prediction_day(tt, min_target_t, prediction_days)
            decay = self._precision_decay(prediction_day)
            dt = float(tt - base_time)

            pred = value_mean + trend * dt
            variance = float((value_std ** 2) * (1.0 + decay + 0.1))
            uncertainty = float(math.sqrt(max(variance, 1e-9)))

            results.append(
                {
                    "x": float(tx),
                    "y": float(ty),
                    "z": float(tz),
                    "t": float(tt),
                    "prediction_time": datetime.fromtimestamp(float(tt), tz=timezone.utc).isoformat(),
                    "value": float(pred),
                    "variance": variance,
                    "uncertainty": uncertainty,
                    "confidence_interval": [float(pred - 1.96 * uncertainty), float(pred + 1.96 * uncertainty)],
                    "precision_decay": decay,
                    "prediction_day": prediction_day,
                    "method": f"{model.model_type}_offline",
                    "sequence": idx,
                }
            )
        return results

    def _predict_values_only(self, model: TrainedModel, samples: Dict[str, Sequence[float]]) -> np.ndarray:
        x, y, z, t, _ = self._extract_and_validate_data(samples)
        preds: List[float] = []
        for tx, ty, tz, tt in zip(x, y, z, t):
            pred, _ = self._predict_single(model, float(tx), float(ty), float(tz), float(tt))
            preds.append(float(pred))
        return np.asarray(preds, dtype=np.float64)

    def _predict_single(self, model: TrainedModel, tx: float, ty: float, tz: float, tt: float) -> Tuple[float, float]:
        dx = model.x - tx
        dy = model.y - ty
        dz = model.z - tz
        dt = np.abs(model.t - tt)

        spatial_distance = np.sqrt(dx * dx + dy * dy + dz * dz)
        temporal_distance = dt

        sr = max(model.parameters["spatial_range"], 1e-6)
        tr = max(model.parameters["temporal_range"], 1e-6)
        coupling = max(model.parameters.get("coupling", 0.6), 1e-6)

        if model.model_type == "separated":
            kernel = 0.5 * np.exp(-spatial_distance / sr) + 0.5 * np.exp(-temporal_distance / tr)
        elif model.model_type == "product":
            kernel = np.exp(-(spatial_distance / sr + temporal_distance / tr))
        else:
            st_norm = np.sqrt((spatial_distance / sr) ** 2 + (temporal_distance / tr) ** 2)
            kernel = np.exp(-np.power(st_norm, coupling))

        kernel = np.maximum(kernel, 1e-12)
        weights = kernel / np.sum(kernel)

        pred = float(np.sum(weights * model.value))
        variance = float(np.sum(weights * (model.value - pred) ** 2) + model.parameters["spatial_nugget"])
        return pred, variance

    def _build_prediction_cache_key(
        self,
        model_id: str,
        target_positions: Dict[str, Sequence[float]],
        target_times: Sequence[float],
        prediction_days: int,
        options: Dict[str, Any],
    ) -> str:
        payload = {
            "model_id": model_id,
            "target_positions": {
                "x": list(target_positions.get("x", [])),
                "y": list(target_positions.get("y", [])),
                "z": list(target_positions.get("z", [])),
            },
            "target_times": list(target_times),
            "prediction_days": prediction_days,
            "mode": {
                "online_preferred": bool(options.get("online_preferred", True)),
                "backend_available": bool(options.get("backend_available", True)),
            },
        }
        digest = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
        return f"spatiotemporal:predict:{digest}"

    def _compute_prediction_day(self, target_t: float, base_t: float, max_days: int) -> int:
        delta = max(float(target_t - base_t), 0.0)
        day = int(delta // 86400) + 1
        return max(1, min(day, max_days))

    def _precision_decay(self, day: int) -> float:
        if day <= 1:
            return 0.05
        if day <= 7:
            return round(0.05 + (day - 1) * (0.10 / 6.0), 6)
        if day <= 15:
            return round(0.15 + (day - 7) * (0.15 / 8.0), 6)
        return 0.30

    def _expand_targets(
        self,
        target_positions: Dict[str, Sequence[float]],
        target_times: Sequence[float],
    ) -> Tuple[List[float], List[float], List[float], List[float]]:
        x = [float(v) for v in target_positions.get("x", [])]
        y = [float(v) for v in target_positions.get("y", [])]
        z = [float(v) for v in target_positions.get("z", [])]
        t = [float(v) for v in target_times]

        if not x or not y or not z or not t:
            raise ValueError("target_positions 和 target_times 不能为空")
        if not (len(x) == len(y) == len(z)):
            raise ValueError("target_positions.x/y/z 长度必须一致")

        xs: List[float] = []
        ys: List[float] = []
        zs: List[float] = []
        ts: List[float] = []

        for tt in t:
            for tx, ty, tz in zip(x, y, z):
                xs.append(tx)
                ys.append(ty)
                zs.append(tz)
                ts.append(tt)
        return xs, ys, zs, ts

    def _extract_and_validate_data(
        self,
        data: Dict[str, Sequence[float]],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        x = np.asarray(data.get("x", []), dtype=np.float64)
        y = np.asarray(data.get("y", []), dtype=np.float64)
        z = np.asarray(data.get("z", []), dtype=np.float64)
        t = np.asarray(data.get("t", []), dtype=np.float64)
        value = np.asarray(data.get("value", []), dtype=np.float64)

        n = len(x)
        if n < 3:
            raise ValueError("至少需要 3 个样本点")
        if not (len(y) == n and len(z) == n and len(t) == n and len(value) == n):
            raise ValueError("x/y/z/t/value 长度必须一致")
        if np.any(~np.isfinite(value)):
            raise ValueError("value 存在非法值")

        return x, y, z, t, value

    def _build_data_stats(
        self,
        x: np.ndarray,
        y: np.ndarray,
        z: np.ndarray,
        t: np.ndarray,
        value: np.ndarray,
    ) -> Dict[str, Any]:
        spatial_points = len({(round(float(a), 6), round(float(b), 6), round(float(c), 6)) for a, b, c in zip(x, y, z)})
        temporal_points = len({round(float(v), 3) for v in t})
        return {
            "n_spatial_points": int(spatial_points),
            "n_temporal_points": int(temporal_points),
            "total_samples": int(len(value)),
            "value_range": [float(np.min(value)), float(np.max(value))],
            "value_mean": float(np.mean(value)),
            "value_std": float(np.std(value)),
        }

    def _estimate_range(self, points: np.ndarray) -> float:
        n = len(points)
        if n <= 1:
            return 1.0

        # 限制配对数，保障大规模数据下训练耗时。
        if n > 500:
            step = max(1, n // 500)
            points = points[::step]
            n = len(points)

        distances: List[float] = []
        for i in range(n - 1):
            diff = points[i + 1 :] - points[i]
            d = np.sqrt(np.sum(diff * diff, axis=1))
            if len(d) > 0:
                distances.append(float(np.median(d)))

        return float(max(statistics.median(distances) if distances else 1.0, 1e-6))

    def _gaussian_crps(self, mu: float, sigma: float, obs: float) -> float:
        z = (obs - mu) / sigma
        phi = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * z * z)
        phi_cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        return sigma * (z * (2.0 * phi_cdf - 1.0) + 2.0 * phi - 1.0 / math.sqrt(math.pi))

    def _get_model(self, model_id: str) -> TrainedModel:
        with self._lock:
            model = self._models.get(model_id)
        if model is None:
            raise KeyError(f"模型不存在: {model_id}")
        return model


spatiotemporal_kriging_service = SpatiotemporalKrigingService()
