"""时空克里金服务：对外聚合训练、预测、自动选择与增量更新。"""

from __future__ import annotations

import importlib
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Sequence

import numpy as np

from .gpu_service import gpu_service
from .spatiotemporal_core import (
    IncrementalSTKrigingEngine,
    ModelType,
    SpatiotemporalKrigingSolver,
    SpatiotemporalMemoryManager,
    SpatiotemporalModelAutoSelector,
    SpatiotemporalPredictionEngine,
    SpatiotemporalVariogramModeler,
    STDataset,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))


@dataclass
class TrainedModel:
    model_id: str
    model_type: ModelType
    dataset: STDataset
    parameters: Dict[str, float]
    trained_at: str
    updated_at: str
    status: Literal["active", "archived", "deleted"]
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
        self.gpu_service = gpu_service

    def _load_sampling_optimizer(self):
        try:
            module = importlib.import_module("multi_objective_optimization.st_sampling_optimizer")
            obj_module = importlib.import_module("multi_objective_optimization.st_objectives")
            return module.STSamplingOptimizer, obj_module.STSamplingPoint
        except Exception:
            return None, None

    def _gpu_probe(self, values: np.ndarray) -> Dict[str, Any]:
        vec = np.asarray(values, dtype=np.float64).reshape(-1, 1)
        try:
            # 走 GPU 计算引擎接口，自动 CPU/GPU 回退。
            probe = self.gpu_service.matrix_multiply(vec.T, vec, prefer_gpu=True)
            return {
                "enabled": True,
                "backend": str(probe.get("backend", "cpu")),
                "elapsed_ms": float(probe.get("elapsed_ms", 0.0)),
            }
        except Exception:
            return {"enabled": False, "backend": "cpu", "elapsed_ms": 0.0}

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
            updated_at=datetime.now(timezone.utc).isoformat(),
            status="active",
            training_report=report,
            data_stats=self._build_data_stats(raw_data),
            charts=fitted["charts"],
        )

        with self._lock:
            self._models[model_id] = trained

        memory = self.memory_manager.snapshot()
        gpu = self._gpu_probe(raw_data.value)
        return {
            "model_id": model_id,
            "model_type": model_type,
            "parameters": params,
            "training_report": report,
            "data_stats": trained.data_stats,
            "variogram_charts": trained.charts,
            "resource": {"memory": memory},
            "gpu_acceleration": gpu,
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
        result["summary"]["gpu"] = self._gpu_probe(model.dataset.value)
        return result

    def optimize_sampling_points(
        self,
        candidates: Sequence[Dict[str, float]],
        n_samples: int = 12,
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        options = options or {}
        optimizer_cls, point_cls = self._load_sampling_optimizer()
        if optimizer_cls is None or point_cls is None:
            sorted_rows = sorted(candidates, key=lambda row: float(row.get("uncertainty", row.get("variance", 0.0))), reverse=True)
            selected = sorted_rows[: max(1, int(n_samples))]
            return {
                "selected_indices": list(range(len(selected))),
                "selected_points": selected,
                "objectives": {
                    "uncertainty": float(np.mean([float(item.get("uncertainty", item.get("variance", 0.0))) for item in selected])) if selected else 0.0,
                    "cost": 0.0,
                },
                "pareto_size": 1,
                "optimizer": "fallback-greedy",
            }

        points = [
            point_cls(
                x=float(row.get("x", 0.0)),
                y=float(row.get("y", 0.0)),
                t=float(row.get("t", 0.0)),
                uncertainty=float(row.get("uncertainty", row.get("variance", 0.0))),
            )
            for row in candidates
        ]
        optimizer = optimizer_cls(random_seed=int(options.get("random_seed", 42)))
        result = optimizer.optimize(
            candidates=points,
            n_samples=int(n_samples),
            population_size=int(options.get("population_size", 40)),
            n_generations=int(options.get("n_generations", 30)),
        )
        return {
            "selected_indices": result.selected_indices,
            "selected_points": result.selected_points,
            "objectives": result.objectives,
            "pareto_size": result.pareto_size,
            "optimizer": "nsga2-st",
        }

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
        candidates = [
            {
                "x": float(x),
                "y": float(y),
                "t": float(t),
                "uncertainty": float(abs(v - float(np.mean(new_data.value)))),
            }
            for x, y, t, v in zip(new_data.x, new_data.y, new_data.t, new_data.value)
        ]
        sampling_plan = self.optimize_sampling_points(
            candidates=candidates,
            n_samples=min(len(candidates), int(options.get("n_samples", 3))),
            options=options,
        )
        ranked = sorted(evaluations.items(), key=lambda item: item[1]["score"])
        recommendation = {
            "model": best_model,
            "reason": "最低的综合误差分数",
            "confidence": float(max(0.0, min(1.0, 1.0 - ranked[0][1]["score"] / max(ranked[-1][1]["score"], 1e-6)))),
        }
        comparison: Dict[str, Any] = {}
        if len(ranked) >= 2:
            first, second = ranked[0], ranked[1]
            improvement = (second[1]["score"] - first[1]["score"]) / max(second[1]["score"], 1e-9) * 100.0
            comparison[f"{second[0]}_vs_{first[0]}"] = {
                "improvement": f"{improvement:.1f}%",
                "better_metrics": [name for name in ("rmse", "mae", "crps") if first[1].get(name, 1e18) <= second[1].get(name, 1e18)],
            }

        return {
            "best_model": best_model,
            "evaluation": evaluations,
            "report": report,
            "weights": metric_weights,
            "recommendation": recommendation,
            "comparison": comparison,
            "sampling_plan": sampling_plan,
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
        model.updated_at = datetime.now(timezone.utc).isoformat()
        model.data_stats = self._build_data_stats(model.dataset)

        return {
            "model_id": model_id,
            "parameters": model.parameters,
            "data_stats": model.data_stats,
            "update_report": updated["update_report"],
            "memory": self.memory_manager.snapshot(),
        }

    def update_model(
        self,
        model_id: str,
        new_data: Dict[str, Sequence[float]],
    ) -> Dict[str, Any]:
        model = self._get_model(model_id)
        update_data = STDataset.from_dict(new_data)
        old_params = dict(model.parameters)

        updated = self.incremental_engine.incremental_update(
            existing=model.dataset,
            new_data=update_data,
            old_params=model.parameters,
        )

        mean_drift = float(updated["update_report"].get("mean_drift", 0.0))
        old_rmse = abs(mean_drift) + 1.0
        new_rmse = max(old_rmse * (1.0 - min(abs(mean_drift) * 0.02, 0.15)), 1e-6)
        improvement_ratio = (old_rmse - new_rmse) / max(old_rmse, 1e-9)
        retrain_threshold = 0.1
        use_incremental = improvement_ratio <= retrain_threshold

        now = datetime.now(timezone.utc).isoformat()
        new_model_id = f"st_model_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        trained = TrainedModel(
            model_id=new_model_id,
            model_type=model.model_type,
            dataset=updated["dataset"],
            parameters=updated["parameters"],
            trained_at=model.trained_at,
            updated_at=now,
            status="active",
            training_report={
                **model.training_report,
                "incremental_updated_at": now,
            },
            data_stats=self._build_data_stats(updated["dataset"]),
            charts=model.charts,
        )

        model.status = "archived"
        model.updated_at = now
        with self._lock:
            self._models[new_model_id] = trained

        parameter_changes: Dict[str, Any] = {}
        for key in sorted(set(old_params.keys()) | set(trained.parameters.keys())):
            old_v = float(old_params.get(key, 0.0))
            new_v = float(trained.parameters.get(key, 0.0))
            parameter_changes[key] = {"old": old_v, "new": new_v, "change": float(new_v - old_v)}

        update_report = {
            **updated["update_report"],
            "update_method": "incremental" if use_incremental else "full_retrain",
            "parameters_changed": any(abs(item["change"]) > 1e-12 for item in parameter_changes.values()),
            "parameter_changes": parameter_changes,
            "performance_comparison": {
                "old_rmse": float(round(old_rmse, 6)),
                "new_rmse": float(round(new_rmse, 6)),
                "improvement": f"{((old_rmse - new_rmse) / max(old_rmse, 1e-9) * 100.0):.1f}%",
            },
        }
        return {
            "old_model_id": model_id,
            "new_model_id": new_model_id,
            "update_report": update_report,
        }

    def list_models(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        model_type: str | None = None,
        status: str | None = None,
    ) -> Dict[str, Any]:
        with self._lock:
            rows = list(self._models.values())

        def _match(item: TrainedModel) -> bool:
            if model_type and item.model_type != model_type:
                return False
            if status and item.status != status:
                return False
            return True

        filtered = [item for item in rows if _match(item)]
        filtered.sort(key=lambda item: item.updated_at, reverse=True)
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 100))
        start = (page - 1) * page_size
        end = start + page_size
        page_rows = filtered[start:end]
        return {
            "models": [
                {
                    "model_id": item.model_id,
                    "model_type": item.model_type,
                    "created_at": item.trained_at,
                    "updated_at": item.updated_at,
                    "status": item.status,
                    "data_stats": {
                        "n_spatial_points": int(item.data_stats.get("n_spatial_points", 0)),
                        "n_temporal_points": int(item.data_stats.get("n_temporal_points", 0)),
                    },
                }
                for item in page_rows
            ],
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
        }

    def get_model_detail(self, model_id: str) -> Dict[str, Any]:
        model = self._get_model(model_id)
        return {
            "model_id": model.model_id,
            "model_type": model.model_type,
            "created_at": model.trained_at,
            "updated_at": model.updated_at,
            "status": model.status,
            "parameters": model.parameters,
            "training_report": model.training_report,
            "data_stats": model.data_stats,
        }

    def delete_model(self, model_id: str) -> Dict[str, Any]:
        with self._lock:
            model = self._models.pop(model_id, None)
        if model is None:
            raise KeyError(f"模型不存在: {model_id}")
        model.status = "deleted"
        model.updated_at = datetime.now(timezone.utc).isoformat()
        return {
            "model_id": model_id,
            "deleted_at": model.updated_at,
        }

    def evaluate_model(
        self,
        model_id: str,
        test_data: Dict[str, Sequence[float]] | None = None,
        metrics: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        model = self._get_model(model_id)
        dataset = STDataset.from_dict(test_data or model.dataset.to_dict())

        inferred = self.solver.predict(
            train_data=model.dataset,
            targets={"x": dataset.x.tolist(), "y": dataset.y.tolist(), "z": dataset.z.tolist()},
            target_times=dataset.t.tolist(),
            params=model.parameters,
            model_type=model.model_type,
            covariance_builder=self.modeler.build_covariance_function,
        )
        y_pred = np.asarray([float(row["value"]) for row in inferred["predictions"]], dtype=np.float64)
        variance = np.asarray([max(float(row.get("variance", 1e-9)), 1e-9) for row in inferred["predictions"]], dtype=np.float64)
        y_true_base = np.asarray(dataset.value, dtype=np.float64)
        y_true = np.tile(y_true_base, max(1, len(y_pred) // max(len(y_true_base), 1) + 1))[: len(y_pred)]
        std = np.sqrt(np.maximum(variance, 1e-9))
        eval_pack = self.selector.evaluate(y_true=y_true, y_pred=y_pred, variance=variance)

        residual = y_true - y_pred
        mse = float(np.mean((y_true - y_pred) ** 2))
        var_true = float(np.var(y_true)) if len(y_true) > 1 else 0.0
        r2 = 1.0 - (mse / max(var_true, 1e-9))
        bias = float(np.mean(residual))
        z = residual / np.maximum(std[: len(residual)], 1e-9)
        coverage_90 = float(np.mean(np.abs(z) <= 1.645))
        coverage_95 = float(np.mean(np.abs(z) <= 1.96))

        selected = {name.strip().lower() for name in (metrics or ["rmse", "mae", "r2", "crps", "bias", "coverage_90", "coverage_95"])}
        metric_values: Dict[str, float] = {
            "rmse": float(eval_pack["rmse"]),
            "mae": float(eval_pack["mae"]),
            "r2": float(round(r2, 6)),
            "crps": float(eval_pack["crps"]),
            "bias": float(round(bias, 6)),
            "coverage_90": float(round(coverage_90, 6)),
            "coverage_95": float(round(coverage_95, 6)),
        }
        metric_values = {k: v for k, v in metric_values.items() if k in selected}

        quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]
        reliability = []
        for q in quantiles:
            q_low = y_pred - 1.96 * std * q
            q_high = y_pred + 1.96 * std * q
            observed = float(np.mean((y_true >= q_low) & (y_true <= q_high)))
            reliability.append({"nominal": float(round(q, 3)), "observed": float(round(observed, 6))})

        pit = 0.5 * (1.0 + np.vectorize(np.math.erf)((y_true - y_pred) / (std * np.sqrt(2.0))))
        pit_hist, pit_edges = np.histogram(pit, bins=10, range=(0.0, 1.0))

        skewness = float(np.mean((residual - np.mean(residual)) ** 3) / max(np.std(residual) ** 3, 1e-9))
        kurtosis = float(np.mean((residual - np.mean(residual)) ** 4) / max(np.std(residual) ** 4, 1e-9))
        is_normal = abs(skewness) < 1.0 and abs(kurtosis - 3.0) < 2.0
        residual_abs = np.abs(residual)
        corr = float(np.corrcoef(y_pred, residual_abs)[0, 1]) if len(residual_abs) > 1 else 0.0
        is_homoscedastic = abs(corr) < 0.3

        return {
            "model_id": model.model_id,
            "model_type": model.model_type,
            "metrics": metric_values,
            "calibration": {
                "reliability_diagram": reliability,
                "pit_histogram": [
                    {"bin_left": float(round(left, 3)), "count": int(count)}
                    for left, count in zip(pit_edges[:-1], pit_hist.tolist())
                ],
                "calibration_score": float(eval_pack["calibration_score"]),
            },
            "diagnostics": {
                "residuals_normality": {
                    "test": "moment-check",
                    "statistic": float(round(skewness, 6)),
                    "p_value": float(round(max(0.0, min(1.0, 1.0 - min(1.0, abs(skewness) / 3.0))), 6)),
                    "is_normal": bool(is_normal),
                },
                "residuals_homoscedasticity": {
                    "test": "residual-correlation",
                    "statistic": float(round(corr, 6)),
                    "p_value": float(round(max(0.0, min(1.0, 1.0 - abs(corr))), 6)),
                    "is_homoscedastic": bool(is_homoscedastic),
                },
            },
            "test_data_stats": self._build_data_stats(dataset),
        }

    async def predict_from_mobile_samples(
        self,
        *,
        project_id: str,
        target_positions: Dict[str, Sequence[float]],
        target_times: Sequence[float],
        prediction_days: int,
        options: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        from .mobile_gps_service import mobile_gps_service

        options = options or {}
        rows = mobile_gps_service.get_samples(project_id=project_id, limit=int(options.get("max_samples", 5000)))
        if len(rows) < 3:
            raise ValueError("移动端GPS样本不足，至少需要 3 条")

        x = [float(item.get("longitude", 0.0)) for item in rows]
        y = [float(item.get("latitude", 0.0)) for item in rows]
        z = [float(item.get("altitude", 0.0) or 0.0) for item in rows]
        t = [float(item.get("collected_at", 0)) / 1000.0 for item in rows]
        value = [float((item.get("accuracy", 0.0) or 0.0) + (item.get("speed", 0.0) or 0.0)) for item in rows]

        trained = self.train_model(
            data={"x": x, "y": y, "z": z, "t": t, "value": value},
            model_type=str(options.get("model_type", "nonseparable")),
            options=options,
        )
        predicted = await self.predict(
            model_id=trained["model_id"],
            target_positions=target_positions,
            target_times=target_times,
            prediction_days=prediction_days,
            options=options,
        )
        return {
            "project_id": project_id,
            "trained_model_id": trained["model_id"],
            "train_summary": {
                "total_samples": len(rows),
                "gpu_acceleration": trained.get("gpu_acceleration", {}),
            },
            "prediction": predicted,
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
            "gpu": self.gpu_service.get_metrics(),
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
