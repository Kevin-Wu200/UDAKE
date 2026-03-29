"""高级缓存策略测试。"""

import pytest

from app.services.cache_service import (
    CacheService,
    MemoryCacheBackend,
    MultiLevelCacheBackend,
)


@pytest.mark.asyncio
async def test_multilevel_backend_promotes_l2_hits_to_l1():
    l1 = MemoryCacheBackend()
    l2 = MemoryCacheBackend()
    backend = MultiLevelCacheBackend(l1_backend=l1, l2_backend=l2)

    await l2.set("k", {"value": 1}, ttl=60)
    assert await l1.get("k") is None

    fetched = await backend.get("k")
    assert fetched == {"value": 1}
    assert await l1.get("k") == {"value": 1}


@pytest.mark.asyncio
async def test_cache_service_supports_sharding_and_pattern_invalidation():
    service = CacheService(
        backend=MemoryCacheBackend(),
        max_size=50,
        shard_count=4,
        auto_tune=False,
    )

    await service.set("user:1", {"name": "u1"})
    await service.set("user:2", {"name": "u2"})
    await service.set("product:1", {"name": "p1"})

    assert service.resolve_storage_key("user:1").startswith("s")

    await service.invalidate_pattern("user:")
    assert await service.get("user:1") is None
    assert await service.get("user:2") is None
    assert await service.get("product:1") == {"name": "p1"}


@pytest.mark.asyncio
async def test_cache_service_compression_roundtrip():
    service = CacheService(
        backend=MemoryCacheBackend(),
        max_size=20,
        enable_compression=True,
        compression_threshold=64,
        auto_tune=False,
    )
    payload = {
        "dataset": "cache-advanced",
        "values": ["x" * 128 for _ in range(64)],
    }

    await service.set("large", payload, ttl=60)
    storage_key = service.resolve_storage_key("large")
    raw = await service.backend.get(storage_key)

    assert isinstance(raw, dict)
    assert raw.get("__udake_cache_meta__", {}).get("compressed") is True
    assert await service.get("large") == payload

    stats = service.get_stats()
    assert stats["compressions"] >= 1
    assert stats["compression_saved_bytes"] > 0


@pytest.mark.asyncio
async def test_cache_service_lfu_eviction():
    service = CacheService(
        backend=MemoryCacheBackend(),
        max_size=2,
        eviction_policy="lfu",
        enable_compression=False,
        auto_tune=False,
    )

    await service.set("k1", "v1", ttl=60)
    await service.set("k2", "v2", ttl=60)
    assert await service.get("k1") == "v1"
    assert await service.get("k1") == "v1"

    await service.set("k3", "v3", ttl=60)

    assert await service.get("k2") is None
    assert await service.get("k1") == "v1"
    assert await service.get("k3") == "v3"
    assert service.get_stats()["evictions"] >= 1


@pytest.mark.asyncio
async def test_cache_service_auto_tuning_expands_capacity_when_needed():
    service = CacheService(
        backend=MemoryCacheBackend(),
        max_size=5,
        auto_tune=True,
        min_cache_size=3,
        max_cache_size_limit=16,
        tune_request_interval=10,
        enable_compression=False,
    )

    for i in range(5):
        await service.set(f"hot:{i}", i, ttl=60)

    for i in range(10):
        assert await service.get(f"miss:{i}") is None

    assert service.max_size > 5
    assert service.get_stats()["auto_tune_adjustments"] >= 1


@pytest.mark.asyncio
async def test_cache_service_snapshot_backup_and_restore():
    service = CacheService(
        backend=MemoryCacheBackend(),
        max_size=20,
        shard_count=2,
        auto_tune=False,
        enable_compression=True,
        compression_threshold=64,
    )

    await service.set("user:1", {"name": "alice"}, ttl=60)
    await service.set("user:2", {"name": "bob"}, ttl=60)
    await service.set("product:1", {"name": "book"}, ttl=60)

    snapshot = await service.export_snapshot("user:*")
    assert sorted(snapshot["items"].keys()) == ["user:1", "user:2"]

    await service.clear()
    assert await service.get("user:1") is None
    assert await service.get("user:2") is None

    await service.restore_snapshot(snapshot, ttl=60)
    assert await service.get("user:1") == {"name": "alice"}
    assert await service.get("user:2") == {"name": "bob"}
    assert await service.get("product:1") is None
