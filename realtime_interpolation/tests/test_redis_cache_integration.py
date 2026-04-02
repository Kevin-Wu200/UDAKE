"""
Redis 缓存集成测试（使用内存后端降级路径）
"""

import time

from ..cache.redis_cache_manager import RedisCacheManager


class TestRedisCacheIntegration:
    def test_fallback_backend_and_health(self):
        manager = RedisCacheManager(
            redis_url=None,
            host="",
            ttl=30,
            enable_auto_cleanup=False,
        )
        health = manager.check_health()
        assert manager.is_memory_backend is True
        assert health["healthy"] is True
        assert health["backend"] == "memory"

    def test_grid_hash_and_version(self):
        manager = RedisCacheManager(redis_url=None, host="", enable_auto_cleanup=False)
        v1 = manager.set_grid_data("task_a", {"values": [1, 2, 3]}, {"source": "unit"})
        assert v1 == 1
        payload = manager.get_grid_data("task_a")
        assert payload is not None
        assert payload["version"] == 1
        assert payload["grid_data"]["values"] == [1, 2, 3]
        assert payload["metadata"]["source"] == "unit"

    def test_points_zset_and_score_range(self):
        manager = RedisCacheManager(redis_url=None, host="", enable_auto_cleanup=False)
        now = time.time()
        manager.add_sampling_point("task_b", {"x": 1, "y": 1, "v": 10}, score=now - 10)
        manager.add_sampling_point("task_b", {"x": 2, "y": 2, "v": 20}, score=now - 5)
        manager.add_sampling_point("task_b", {"x": 3, "y": 3, "v": 30}, score=now)

        points = manager.get_sampling_points("task_b", start_score=now - 6, end_score=now, limit=2)
        assert len(points) == 2
        assert points[0]["v"] == 20
        assert points[1]["v"] == 30

    def test_history_list_with_trim(self):
        manager = RedisCacheManager(redis_url=None, host="", enable_auto_cleanup=False)
        for i in range(5):
            manager.append_history("task_c", {"index": i}, max_length=3)
        history = manager.get_history("task_c", limit=10)
        assert len(history) == 3
        assert history[0]["event"]["index"] == 2
        assert history[-1]["event"]["index"] == 4

    def test_ttl_expire_for_grid(self):
        manager = RedisCacheManager(redis_url=None, host="", enable_auto_cleanup=False)
        manager.set_grid_data("task_d", {"k": "v"}, ttl=1)
        assert manager.get_grid_data("task_d") is not None
        time.sleep(1.2)
        assert manager.get_grid_data("task_d") is None

    def test_prewarm_by_frequency(self):
        manager = RedisCacheManager(redis_url=None, host="", enable_auto_cleanup=False)

        def loader(task_id: str):
            return {"task": task_id, "cells": [1, 2]}, {"from": "loader"}

        stats = manager.prewarm_by_frequency(
            [("task_1", 10), ("task_2", 30), ("task_3", 20)],
            loader,
            max_tasks=2,
            ttl=30,
        )
        assert stats["total"] == 2
        assert stats["success"] == 2
        assert manager.get_grid_data("task_2") is not None
        assert manager.get_grid_data("task_3") is not None
        assert manager.get_grid_data("task_1") is None

    def test_manual_invalidation_and_notification(self):
        manager = RedisCacheManager(redis_url=None, host="", enable_auto_cleanup=False)
        received = []
        manager.register_invalidation_listener(lambda task_id, reason: received.append((task_id, reason)))

        manager.set_grid_data("task_e", {"x": 1}, ttl=30)
        manager.add_sampling_point("task_e", {"x": 1}, ttl=30)
        manager.append_history("task_e", {"op": "insert"}, ttl=30)
        deleted = manager.invalidate_task("task_e", reason="manual_cleanup", notify=True)

        assert deleted >= 3
        assert manager.get_grid_data("task_e") is None
        assert manager.get_sampling_points("task_e") == []
        assert manager.get_history("task_e") == []
        assert ("task_e", "manual_cleanup") in received

    def test_lock_and_compare_and_set(self):
        manager = RedisCacheManager(redis_url=None, host="", enable_auto_cleanup=False)
        manager.set_grid_data("task_f", {"value": 1}, version=1)

        conflict = manager.compare_and_set_grid(
            "task_f",
            expected_version=0,
            new_grid_data={"value": 2},
        )
        assert conflict["success"] is False
        assert conflict["reason"] == "version_conflict"

        success = manager.compare_and_set_grid(
            "task_f",
            expected_version=1,
            new_grid_data={"value": 3},
            metadata={"op": "cas"},
        )
        assert success["success"] is True
        assert success["new_version"] == 2
        payload = manager.get_grid_data("task_f")
        assert payload is not None
        assert payload["version"] == 2
        assert payload["grid_data"]["value"] == 3
