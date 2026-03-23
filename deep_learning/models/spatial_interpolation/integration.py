"""Integration adapters for realtime interpolation system and service API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from deep_learning.utils.cache import CacheManager


@dataclass
class FusionResult:
    mean: np.ndarray
    variance: np.ndarray
    source: str


class SpatialInterpolationIntegrator:
    """Bridge deep interpolation models with realtime kriging/cache/events."""

    def __init__(self, cache_ttl_seconds: int = 300) -> None:
        # 延迟导入以避免循环导入
        from deep_learning.inference.spatial_interpolation_inference import SpatialInterpolationInference

        self.inference = SpatialInterpolationInference()
        self.cache = CacheManager(ttl_seconds=cache_ttl_seconds)
        self.event_handlers: list[Callable[[dict[str, Any]], None]] = []

    def register_event_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        self.event_handlers.append(handler)

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload}
        for h in self.event_handlers:
            h(event)

    def predict_with_fusion(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray,
        model_type: str = "gnn",
        blend_ratio: float = 0.6,
    ) -> FusionResult:
        cache_key = f"fusion:{model_type}:{hash(query_coords.tobytes())}:{hash(sample_coords.tobytes())}:{hash(sample_values.tobytes())}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            self._emit("cache_hit", {"model": model_type, "size": len(query_coords)})
            return cached

        nn_result = self.inference.predict_batch(
            sample_coords=sample_coords,
            sample_values=sample_values,
            query_coords=query_coords,
            model_type=model_type,
        )

        try:
            from realtime_interpolation.core.incremental_kriging import IncrementalKriging
            from realtime_interpolation.models import BoundingBox, DataPoint, Subscription

            bbox = BoundingBox(
                min_x=float(np.min(sample_coords[:, 0])),
                max_x=float(np.max(sample_coords[:, 0])),
                min_y=float(np.min(sample_coords[:, 1])),
                max_y=float(np.max(sample_coords[:, 1])),
            )
            sub = Subscription(
                subscription_id="dl_fusion",
                data_type="fusion",
                spatial_extent=bbox,
                update_frequency=1,
                interpolation_params={"grid_resolution": 10},
                notification_config={},
            )
            kriging = IncrementalKriging(subscription=sub)
            points = [
                DataPoint(x=float(x), y=float(y), value=float(v), id=f"p{i}")
                for i, ((x, y), v) in enumerate(zip(sample_coords, sample_values))
            ]
            kriging.add_initial_points(points)
            legacy_pred = kriging.predict([(float(x), float(y)) for x, y in query_coords])
            kriging_mean = np.asarray([p.value for p in legacy_pred], dtype=float)
            kriging_var = np.asarray([max(1e-6, p.variance) for p in legacy_pred], dtype=float)
            source = "neural+incremental_kriging"
        except Exception:
            # Fallback when realtime module or heavy deps are unavailable.
            kriging_mean = nn_result.mean
            kriging_var = nn_result.variance
            source = "neural_only"

        ratio = float(np.clip(blend_ratio, 0.0, 1.0))
        mean = ratio * nn_result.mean + (1.0 - ratio) * kriging_mean
        variance = ratio * nn_result.variance + (1.0 - ratio) * kriging_var

        result = FusionResult(mean=mean, variance=np.maximum(variance, 1e-6), source=source)
        self.cache.set(cache_key, result)

        self._emit(
            "interpolation_update",
            {
                "model": model_type,
                "queries": int(len(query_coords)),
                "source": source,
            },
        )
        return result

    def api_predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        coords = np.asarray(payload["sample_coords"], dtype=float)
        values = np.asarray(payload["sample_values"], dtype=float)
        queries = np.asarray(payload["query_coords"], dtype=float)
        model_type = str(payload.get("model_type", "gnn"))
        blend_ratio = float(payload.get("blend_ratio", 0.6))

        result = self.predict_with_fusion(
            sample_coords=coords,
            sample_values=values,
            query_coords=queries,
            model_type=model_type,
            blend_ratio=blend_ratio,
        )
        return {
            "prediction": result.mean.tolist(),
            "variance": result.variance.tolist(),
            "source": result.source,
        }
