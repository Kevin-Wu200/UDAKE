import asyncio

from app.core.spatiotemporal_kriging.st_prediction_engine import STPredictionEngine
import app.services.spatiotemporal_core as st_core


class _FakeCacheService:
    def __init__(self) -> None:
        self._store: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ttl: int = 300):
        self._store[key] = value


async def _run_predict(engine: STPredictionEngine, payload: dict, use_cache: bool = True, online: bool = True):
    counters = {"online": 0, "offline": 0}

    def online_predictor():
        counters["online"] += 1
        return {"model_id": "m1", "predictions": [{"value": 1.0}], "summary": {"total_predictions": 1}}

    def offline_predictor():
        counters["offline"] += 1
        return {"model_id": "m1", "predictions": [{"value": 2.0}], "summary": {"total_predictions": 1}}

    result = await engine.predict(
        model_id="m1",
        payload=payload,
        online_predictor=online_predictor,
        offline_predictor=offline_predictor,
        use_cache=use_cache,
        online_preferred=online,
        backend_available=online,
        cache_ttl=120,
    )
    return result, counters


def test_precision_decay_schedule() -> None:
    engine = STPredictionEngine()
    assert engine.precision_decay(1) == 0.05
    assert 0.05 < engine.precision_decay(7) <= 0.15
    assert 0.15 < engine.precision_decay(15) <= 0.30
    assert engine.precision_decay(30) == 0.30


def test_predict_online_and_cache_hit(monkeypatch, tmp_path) -> None:
    fake_cache = _FakeCacheService()
    monkeypatch.setattr(st_core, "get_cache_service", lambda: fake_cache)

    engine = STPredictionEngine(disk_cache_dir=str(tmp_path / "st_cache"))
    payload = {
        "target_positions": {"x": [120.1], "y": [30.1], "z": [10.1]},
        "target_times": [1712016000.0],
        "prediction_days": 3,
    }

    (first_result, first_mode, first_hit), counters1 = asyncio.run(_run_predict(engine, payload, use_cache=True, online=True))
    assert first_mode == "online"
    assert first_hit is False
    assert first_result["summary"]["cache_hit"] is False
    assert counters1["online"] == 1

    (second_result, second_mode, second_hit), counters2 = asyncio.run(_run_predict(engine, payload, use_cache=True, online=True))
    assert second_mode == "cache"
    assert second_hit is True
    assert second_result["summary"]["cache_hit"] is True
    assert counters2["online"] == 0


def test_predict_offline_and_prefetch_candidates(monkeypatch, tmp_path) -> None:
    fake_cache = _FakeCacheService()
    monkeypatch.setattr(st_core, "get_cache_service", lambda: fake_cache)

    engine = STPredictionEngine(disk_cache_dir=str(tmp_path / "st_cache_2"))
    payload = {
        "target_positions": {"x": [120.1, 120.2], "y": [30.1, 30.2], "z": [10.1, 10.2]},
        "target_times": [1712016000.0],
        "prediction_days": 5,
    }

    (result, mode, hit), counters = asyncio.run(_run_predict(engine, payload, use_cache=False, online=False))
    assert mode == "offline"
    assert hit is False
    assert result["summary"]["mode"] == "offline"
    assert counters["offline"] == 1

    candidates = engine.prefetch_candidates(max_items=1)
    assert len(candidates) == 1
    assert candidates[0]["prediction_days"] == 5


def test_warm_cache_and_policy(monkeypatch, tmp_path) -> None:
    fake_cache = _FakeCacheService()
    monkeypatch.setattr(st_core, "get_cache_service", lambda: fake_cache)

    engine = STPredictionEngine(disk_cache_dir=str(tmp_path / "st_cache_3"))
    entries = [
        {"target_positions": {"x": [1], "y": [1], "z": [1]}, "target_times": [1]},
        {"target_positions": {"x": [2], "y": [2], "z": [2]}, "target_times": [2]},
    ]

    warmed = asyncio.run(engine.warm_cache(entries, predictor=lambda p: {"ok": True, "payload": p}, ttl=30))
    assert warmed == 2

    normal = engine.smart_cache_policy({"target_positions": {"x": [1]}, "target_times": [1]})
    medium = engine.smart_cache_policy({"target_positions": {"x": list(range(50))}, "target_times": [1, 2, 3]})
    high = engine.smart_cache_policy({"target_positions": {"x": list(range(100))}, "target_times": list(range(10))})

    assert normal["priority"] == "normal"
    assert medium["priority"] in {"medium", "high"}
    assert high["priority"] == "high"
