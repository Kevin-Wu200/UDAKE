"""Workflow Redis cache manager tests."""

from __future__ import annotations

import sys
import time
import types

from app.services.workflow_redis_cache import WorkflowRedisCacheManager


def test_workflow_cache_manager_with_fake_redis_pool(monkeypatch):
    calls = {}

    class FakeConnectionPool:
        @classmethod
        def from_url(cls, url: str, **kwargs):
            calls["url"] = url
            calls["kwargs"] = kwargs
            return {"url": url, **kwargs}

    class FakeRedis:
        def __init__(self, connection_pool):
            self.connection_pool = connection_pool
            self._store = {}
            self._expires = {}

        def ping(self):
            return True

        def set(self, key, value, ex=None):
            self._store[key] = value
            if ex is not None:
                self._expires[key] = time.time() + ex
            else:
                self._expires.pop(key, None)
            return True

        def get(self, key):
            exp = self._expires.get(key)
            if exp is not None and exp <= time.time():
                self._store.pop(key, None)
                self._expires.pop(key, None)
                return None
            return self._store.get(key)

        def delete(self, *keys):
            deleted = 0
            for key in keys:
                if key in self._store:
                    deleted += 1
                    self._store.pop(key, None)
                    self._expires.pop(key, None)
            return deleted

        def scan_iter(self, match="*"):
            import fnmatch

            for key in list(self._store.keys()):
                if fnmatch.fnmatch(key, match):
                    yield key

        def expire(self, key, ttl):
            if key not in self._store:
                return False
            self._expires[key] = time.time() + ttl
            return True

        def info(self, section="memory"):
            _ = section
            return {"used_memory": 256, "used_memory_human": "256B", "maxmemory": 0, "mem_fragmentation_ratio": 1}

    fake_module = types.SimpleNamespace(ConnectionPool=FakeConnectionPool, Redis=FakeRedis)
    monkeypatch.setitem(sys.modules, "redis", fake_module)

    manager = WorkflowRedisCacheManager(
        redis_url="redis://localhost:6379/0",
        pool_size=20,
        socket_timeout=5,
        retry_times=3,
    )
    assert manager.is_memory_backend is False
    assert manager.ping() is True

    assert manager.set("workflow:w1", {"name": "wf"}, ttl=60)
    assert manager.get("workflow:w1")["name"] == "wf"
    assert manager.set_many({"a": {"v": 1}, "b": {"v": 2}}, ttl=30) == 2
    assert manager.delete_pattern("w*") == 1

    assert calls["url"] == "redis://localhost:6379/0"
    assert calls["kwargs"]["max_connections"] == 20
    assert calls["kwargs"]["socket_timeout"] == 5
    assert calls["kwargs"]["socket_connect_timeout"] == 5


def test_workflow_cache_manager_retry_and_fallback_memory(monkeypatch):
    class BrokenConnectionPool:
        @classmethod
        def from_url(cls, url: str, **kwargs):
            _ = (url, kwargs)
            raise RuntimeError("redis down")

    fake_module = types.SimpleNamespace(ConnectionPool=BrokenConnectionPool, Redis=object)
    monkeypatch.setitem(sys.modules, "redis", fake_module)

    manager = WorkflowRedisCacheManager(
        redis_url="redis://localhost:6379/0",
        pool_size=10,
        socket_timeout=5,
        retry_times=3,
        strict_redis=False,
    )
    assert manager.is_memory_backend is True

    assert manager.set("user_permissions:u1:wf", {"permissions": ["view"]}, ttl=30)
    assert manager.get("user_permissions:u1:wf")["permissions"] == ["view"]
    deleted = manager.invalidate_cascade(
        "workflow:wf",
        related_patterns=["user_permissions:*:wf", "cursor:wf", "online_users:wf"],
    )
    assert deleted >= 1
