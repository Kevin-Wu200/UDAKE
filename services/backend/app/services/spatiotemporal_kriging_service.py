"""时空克里金服务：对外聚合训练、预测、自动选择与增量更新。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Sequence

import numpy as np

from .spatiotemporal_core import (
    IncrementalSTKrigingEngine,
    ModelType,
    STDataset,
    SpatiotemporalKrigingSolver,
    SpatiotemporalMemoryManager,
    SpatiotemporalModelAutoSelector,
    SpatiotemporalPredictionEngine,
    SpatiotemporalVariogramModeler,
)


@dataclass
class TrainedModel:
    model_id: str
    model_type: ModelType
    dataset: STDataset
    parameters: Dict[str, float]
    trained_at: str
    training_report: Dict[str, Any]
    data_stats: Dict[str, Any]
    charts: Dict[str, Any]


class SpatiotemporalKrigingService:
    """自定义时空克里金引擎服务层。"""

    def __init__(self) -> None:
        self._models: Dict[str, TrainedModel] = {}
        self._lock = threading.Lock()

        self.modeler = SpatiotemporalVariogramModeler()
        self.solver = SpatiotemporalKrigingSolver(block_size=500, temporal_window_size=30, low_rank=100)
        self.selector = SpatiotemporalModelAutoSelector()
        self.prediction_engine = SpatiotemporalPredictionEngine()
        self.incremental_engine = IncrementalSTKrigingEngine()
        self.memory_manager = SpatiotemporalMemoryManager()

    def train_model(
        self,
        data: Dict[str, Sequence[float]],
        model_type: ModelType,
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        options = options or {}
        raw_data = STDataset.from_dict(data)

        fitted = self.modeler.fit(raw_data, model_type)
        params = dict(fitted["parameters"])
        if "coupling" in options:
            params["coupling"] = float(options["coupling"])
        if "beta" in options:
            params["beta"] = float(options["beta"])

        report = dict(fitted["fitting_report"])
        report["training_time"] = float(options.get("training_time", report.get("training_time", 0.0)))
        report["iterations"] = int(options.get("optimization", {}).get("max_iterations", report.get("iterations", 64)))

        model_id = f"st_model_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        trained = TrainedModel(
            model_id=model_id,
            model_type=model_type,
            dataset=raw_data,
            parameters=params,
            trained_at=datetime.now(timezone.utc).isoformat(),
            training_report=report,
            data_stats=self._build_data_stats(raw_data),
            charts=fitted["charts"],
        )

        with self._lock:
            self._models[model_id] = trained

        memory = self.memory_manager.snapshot()
        return {
            "model_id": model_id,
            "model_type": model_type,
            "parameters": params,
            "training_report": report,
            "data_stats": trained.data_stats,
            "variogram_charts": trained.charts,
            "resource": {"memory": memory},
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

        payload = {
            "model_id": model_id,
            "target_positions": {
                "x": [float(v) for v in target_positions.get("x", [])],
                "y": [float(v) for v in target_positions.get("y", [])],
                "z": [float(v) for v in target_positions.get("z", [])],
            },
            "target_times": [float(v) for v in target_times],
            "prediction_days": int(prediction_days),
            "mode": {
                "online_preferred": bool(options.get("online_preferred", True)),
                "backend_available": bool(options.get("backend_available", True)),
            },
        }

        def online_predictor() -> Dict[str, Any]:
            prediction = self.solver.predict(
                train_data=model.dataset,
                targets=target_positions,
                target_times=target_times,
                params=model.parameters,
                model_type=model.model_type,
                covariance_builder=self.modeler.build_covariance_function,
            )
            rows = self._annotate_prediction_rows(
                rows=prediction["predictions"],
                model_type=model.model_type,
                prediction_days=prediction_days,
            )
            return {
                "model_id": model_id,
                "predictions": rows,
                "summary": {
                    "total_predictions": len(rows),
                    "prediction_days": prediction_days,
                    "solver": prediction["solver_info"],
                },
            }

        def offline_predictor() -> Dict[str, Any]:
            rows = self._offline_predict(model, target_positions, target_times, prediction_days)
            return {
                "model_id": model_id,
                "predictions": rows,
                "summary": {
                    "total_predictions": len(rows),
                    "prediction_days": prediction_days,
                    "solver": {"low_rank_used": False, "rank": 0},
                },
            }

        cache_policy = self.prediction_engine.smart_cache_policy(payload)
        result, mode, cache_hit = await self.prediction_engine.predict(
            model_id=model_id,
            payload=payload,
            online_predictor=online_predictor,
            offline_predictor=offline_predictor,
            use_cache=bool(options.get("use_cache", True)),
            online_preferred=bool(options.get("online_preferred", True)),
            backend_available=bool(options.get("backend_available", True)),
            cache_ttl=int(options.get("cache_ttl", cache_policy["cache_ttl"])),
        )

        result.setdefault("summary", {})["mode"] = mode
        result["summary"]["cache_hit"] = cache_hit
        result["summary"]["cache_policy"] = cache_policy
        result["summary"]["performance"] = self.prediction_engine.monitor.snapshot()["cache"]
        result["summary"]["memory"] = self.memory_manager.snapshot()
        return result

    def auto_select_model(
        self,
        historical_data: Dict[str, Sequence[float]],
        new_samples: Dict[str, Sequence[float]],
        prediction_results: Dict[str, List[Dict[str, float]]] | None,
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        options = options or {}
        hist = STDataset.from_dict(historical_data)
        new_data = STDataset.from_dict(new_samples)

        candidate_models: List[ModelType] = ["separated", "product", "nonseparable"]
        evaluations: Dict[str, Dict[str, float]] = {}
        provided = prediction_results or {}

        metric_weights = {
            "rmse": float(options.get("weight_rmse", 0.35)),
            "mae": float(options.get("weight_mae", 0.25)),
            "crps": float(options.get("weight_crps", 0.25)),
            "calibration": float(options.get("weight_calibration", 0.15)),
        }

        for model_name in candidate_models:
            rows = provided.get(model_name)
            if rows:
                y_pred = np.array([float(item.get("predicted", item.get("value", 0.0))) for item in rows], dtype=np.float64)
                variance = np.array([float(item.get("variance", 1.0)) for item in rows], dtype=np.float64)
            else:
                trained = self.train_model(hist.to_dict(), model_name, options={})
                model = self._get_model(trained["model_id"])
                inferred = self.solver.predict(
                    train_data=model.dataset,
                    targets={"x": new_data.x.tolist(), "y": new_data.y.tolist(), "z": new_data.z.tolist()},
                    target_times=new_data.t.tolist(),
                    params=model.parameters,
                    model_type=model.model_type,
                    covariance_builder=self.modeler.build_covariance_function,
                )
                y_pred = np.array([float(item["value"]) for item in inferred["predictions"]], dtype=np.float64)
                variance = np.array([float(item["variance"]) for item in inferred["predictions"]], dtype=np.float64)

            aligned_true = np.tile(new_data.value, max(1, len(y_pred) // max(len(new_data.value), 1) + 1))[: len(y_pred)]
            evaluations[model_name] = self.selector.evaluate(aligned_true, y_pred, variance=variance, weights=metric_weights)

        best_model = self.selector.select_best(evaluations)
        report = self.selector.generate_report(best_model, evaluations)
        return {
            "best_model": best_model,
            "evaluation": evaluations,
            "report": report,
            "weights": metric_weights,
        }

    def incremental_update_model(
        self,
        model_id: str,
        new_data: Dict[str, Sequence[float]],
    ) -> Dict[str, Any]:
        model = self._get_model(model_id)
        update_data = STDataset.from_dict(new_data)

        updated = self.incremental_engine.incremental_update(
            existing=model.dataset,
            new_data=update_data,
            old_params=model.parameters,
        )

        model.dataset = updated["dataset"]
        model.parameters = updated["parameters"]
        model.training_report = {
            **model.training_report,
            "incremental_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        model.data_stats = self._build_data_stats(model.dataset)

        return {
            "model_id": model_id,
            "parameters": model.parameters,
            "data_stats": model.data_stats,
            "update_report": updated["update_report"],
            "memory": self.memory_manager.snapshot(),
        }

    async def warm_prediction_cache(self, model_id: str, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        model = self._get_model(model_id)

        def _predictor(payload: Dict[str, Any]) -> Dict[str, Any]:
            target_positions = payload.get("target_positions", {})
            target_times = payload.get("target_times", [])
            prediction_days = int(payload.get("prediction_days", 7))
            rows = self._offline_predict(model, target_positions, target_times, prediction_days)
            return {
                "model_id": model_id,
                "predictions": rows,
                "summary": {
                    "total_predictions": len(rows),
                    "prediction_days": prediction_days,
                    "solver": {"low_rank_used": False, "rank": 0},
                },
            }

        warmed = await self.prediction_engine.warm_cache(payloads, _predictor, ttl=600)
        return {
            "model_id": model_id,
            "warmed_count": warmed,
            "prefetch_candidates": self.prediction_engine.prefetch_candidates(max_items=5),
        }

    def performance_metrics(self) -> Dict[str, Any]:
        return {
            "prediction_engine": self.prediction_engine.monitor.snapshot(),
            "memory": {
                "latest": self.memory_manager.snapshot(),
                "leak_growth_rate": self.memory_manager.leak_growth_rate(),
            },
        }

    def _annotate_prediction_rows(
        self,
        rows: List[Dict[str, Any]],
        model_type: str,
        prediction_days: int,
    ) -> List[Dict[str, Any]]:
        if not rows:
            return rows
        min_t = min(float(item["t"]) for item in rows)
        annotated: List[Dict[str, Any]] = []
        for seq, item in enumerate(rows, start=1):
            day = int(max(0.0, float(item["t"]) - min_t) // 86400) + 1
            day = max(1, min(day, prediction_days))
            decay = self.prediction_engine.precision_decay(day)
            variance = float(max(float(item["variance"]) * (1.0 + decay), 1e-9))
            uncertainty = float(np.sqrt(variance))
            value = float(item["value"])
            annotated.append(
                {
                    "x": float(item["x"]),
                    "y": float(item["y"]),
                    "z": float(item["z"]),
                    "t": float(item["t"]),
                    "prediction_time": datetime.fromtimestamp(float(item["t"]), tz=timezone.utc).isoformat(),
                    "value": value,
                    "variance": variance,
                    "uncertainty": uncertainty,
                    "confidence_interval": [float(value - 1.96 * uncertainty), float(value + 1.96 * uncertainty)],
                    "precision_decay": decay,
                    "prediction_day": day,
                    "method": model_type,
                    "sequence": seq,
                }
            )
        return annotated

    def _offline_predict(
        self,
        model: TrainedModel,
        target_positions: Dict[str, Sequence[float]],
        target_times: Sequence[float],
        prediction_days: int,
    ) -> List[Dict[str, Any]]:
        tx = np.asarray(target_positions.get("x", []), dtype=np.float64)
        ty = np.asarray(target_positions.get("y", []), dtype=np.float64)
        tz = np.asarray(target_positions.get("z", []), dtype=np.float64)
        tt = np.asarray(target_times, dtype=np.float64)
        if len(tx) == 0 or len(tt) == 0:
            raise ValueError("target_positions 和 target_times 不能为空")

        mean = float(np.mean(model.dataset.value))
        std = float(np.std(model.dataset.value))
        if len(model.dataset.t) > 1:
            trend = float((model.dataset.value[-1] - model.dataset.value[0]) / max(model.dataset.t[-1] - model.dataset.t[0], 1.0))
        else:
            trend = 0.0
        base_t = float(np.max(model.dataset.t))
        min_t = float(np.min(tt))

        rows: List[Dict[str, Any]] = []
        seq = 1
        for t_value in tt:
            for x, y, z in zip(tx, ty, tz):
                day = int(max(0.0, float(t_value) - min_t) // 86400) + 1
                day = max(1, min(day, prediction_days))
                decay = self.prediction_engine.precision_decay(day)

                value = mean + trend * float(t_value - base_t)
                variance = float(max((std**2) * (1.1 + decay), 1e-9))
                unc = float(np.sqrt(variance))
                rows.append(
                    {
                        "x": float(x),
                        "y": float(y),
                        "z": float(z),
                        "t": float(t_value),
                        "prediction_time": datetime.fromtimestamp(float(t_value), tz=timezone.utc).isoformat(),
                        "value": float(value),
                        "variance": variance,
                        "uncertainty": unc,
                        "confidence_interval": [float(value - 1.96 * unc), float(value + 1.96 * unc)],
                        "precision_decay": decay,
                        "prediction_day": day,
                        "method": f"{model.model_type}_offline",
                        "sequence": seq,
                    }
                )
                seq += 1
        return rows

    def _build_data_stats(self, data: STDataset) -> Dict[str, Any]:
        spatial_points = len({(round(float(a), 6), round(float(b), 6), round(float(c), 6)) for a, b, c in zip(data.x, data.y, data.z)})
        temporal_points = len({round(float(v), 3) for v in data.t})
        return {
            "n_spatial_points": int(spatial_points),
            "n_temporal_points": int(temporal_points),
            "total_samples": int(len(data.value)),
            "value_range": [float(np.min(data.value)), float(np.max(data.value))],
            "value_mean": float(np.mean(data.value)),
            "value_std": float(np.std(data.value)),
        }

    def _get_model(self, model_id: str) -> TrainedModel:
        with self._lock:
            model = self._models.get(model_id)
        if model is None:
            raise KeyError(f"模型不存在: {model_id}")
        return model


spatiotemporal_kriging_service = SpatiotemporalKrigingService()
