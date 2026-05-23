"""
缓存服务
支持内存缓存和Redis缓存
"""

from __future__ import annotations

import asyncio
import base64
import fnmatch
import hashlib
import json
import re
import threading
import time
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

_CACHE_ENVELOPE_KEY = "__udake_cache_meta__"
_CACHE_ENVELOPE_FORMAT = "zlib+base64+json"


class CacheBackend(ABC):
    """缓存后端接口"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = None):
        pass

    @abstractmethod
    async def delete(self, key: str):
        pass

    @abstractmethod
    async def clear(self):
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    async def get_size(self) -> int:
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        pass


class MemoryCacheBackend(CacheBackend):
    """内存缓存后端"""

    def __init__(self):
        self.cache: Dict[str, tuple] = {}
        self.lock = threading.Lock()

    async def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                value, expires_at = self.cache[key]
                if datetime.now() < expires_at:
                    return value
                else:
                    del self.cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = None):
        with self.lock:
            if ttl is None:
                ttl = 300  # 默认5分钟
            expires_at = datetime.now() + timedelta(seconds=ttl)
            self.cache[key] = (value, expires_at)

    async def delete(self, key: str):
        with self.lock:
            if key in self.cache:
                del self.cache[key]

    async def clear(self):
        with self.lock:
            self.cache.clear()

    async def exists(self, key: str) -> bool:
        with self.lock:
            if key in self.cache:
                _, expires_at = self.cache[key]
                if datetime.now() < expires_at:
                    return True
                else:
                    del self.cache[key]
        return False

    async def get_size(self) -> int:
        with self.lock:
            # 清理过期项
            now = datetime.now()
            expired_keys = [
                key for key, (_, expires_at) in self.cache.items()
                if now >= expires_at
            ]
            for key in expired_keys:
                del self.cache[key]
            return len(self.cache)

    async def keys(self, pattern: str = "*") -> List[str]:
        with self.lock:
            now = datetime.now()
            expired_keys = [
                key for key, (_, expires_at) in self.cache.items()
                if now >= expires_at
            ]
            for key in expired_keys:
                del self.cache[key]
            if not pattern or pattern == "*":
                return list(self.cache.keys())
            return [key for key in self.cache.keys() if fnmatch.fnmatch(key, pattern)]


class RedisCacheBackend(CacheBackend):
    """Redis缓存后端"""

    def __init__(self, host='localhost', port=6379, db=0):
        try:
            import redis
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True
            )
            # 测试连接
            self.client.ping()
            print("[缓存服务] Redis连接成功")
        except ImportError:
            raise ImportError("Redis is not installed. Install it with: pip install redis")
        except Exception as e:
            print(f"[缓存服务] Redis连接失败: {e}")
            raise

    async def get(self, key: str) -> Optional[Any]:
        loop = asyncio.get_event_loop()
        value = await loop.run_in_executor(None, self.client.get, key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(self, key: str, value: Any, ttl: int = None):
        loop = asyncio.get_event_loop()
        try:
            serialized = json.dumps(value, default=str)
        except (TypeError, ValueError):
            serialized = str(value)

        if ttl:
            await loop.run_in_executor(None, self.client.setex, key, ttl, serialized)
        else:
            await loop.run_in_executor(None, self.client.set, key, serialized)

    async def delete(self, key: str):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.client.delete, key)

    async def clear(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.client.flushdb)

    async def exists(self, key: str) -> bool:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.client.exists, key)
        return result > 0

    async def get_size(self) -> int:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self.client.dbsize)
        return result

    async def keys(self, pattern: str = "*") -> List[str]:
        loop = asyncio.get_event_loop()
        scanned = await loop.run_in_executor(
            None,
            lambda: list(self.client.scan_iter(match=pattern or "*"))
        )
        return [str(key) for key in scanned]


class MultiLevelCacheBackend(CacheBackend):
    """多级缓存后端（L1 + L2）"""

    def __init__(
        self,
        l1_backend: CacheBackend,
        l2_backend: Optional[CacheBackend] = None,
        promote_on_l2_hit: bool = True
    ):
        self.l1_backend = l1_backend
        self.l2_backend = l2_backend
        self.promote_on_l2_hit = promote_on_l2_hit

    async def get(self, key: str) -> Optional[Any]:
        value = await self.l1_backend.get(key)
        if value is not None:
            return value

        if self.l2_backend is None:
            return None

        value = await self.l2_backend.get(key)
        if value is not None and self.promote_on_l2_hit:
            await self.l1_backend.set(key, value)
        return value

    async def set(self, key: str, value: Any, ttl: int = None):
        await self.l1_backend.set(key, value, ttl)
        if self.l2_backend is not None:
            await self.l2_backend.set(key, value, ttl)

    async def delete(self, key: str):
        await self.l1_backend.delete(key)
        if self.l2_backend is not None:
            await self.l2_backend.delete(key)

    async def clear(self):
        await self.l1_backend.clear()
        if self.l2_backend is not None:
            await self.l2_backend.clear()

    async def exists(self, key: str) -> bool:
        if await self.l1_backend.exists(key):
            return True
        if self.l2_backend is None:
            return False
        return await self.l2_backend.exists(key)

    async def get_size(self) -> int:
        if self.l2_backend is None:
            return await self.l1_backend.get_size()
        keys = set(await self.l1_backend.keys("*"))
        keys.update(await self.l2_backend.keys("*"))
        return len(keys)

    async def keys(self, pattern: str = "*") -> List[str]:
        keys = set(await self.l1_backend.keys(pattern))
        if self.l2_backend is not None:
            keys.update(await self.l2_backend.keys(pattern))
        return list(keys)


@dataclass
class CacheServiceConfig:
    """缓存配置管理"""

    max_size: int = 1000
    shard_count: int = 1
    eviction_policy: str = "adaptive"
    enable_compression: bool = True
    compression_threshold: int = 2048
    auto_tune: bool = True
    min_cache_size: Optional[int] = None
    max_cache_size_limit: Optional[int] = None
    tune_request_interval: int = 200

    @classmethod
    def from_settings(cls, settings: Any) -> "CacheServiceConfig":
        max_size = int(getattr(settings, "CACHE_MAX_SIZE", 1000))
        min_size = getattr(settings, "CACHE_MIN_SIZE", None)
        max_limit = getattr(settings, "CACHE_MAX_SIZE_LIMIT", None)
        return cls(
            max_size=max_size,
            shard_count=int(getattr(settings, "CACHE_SHARD_COUNT", 1)),
            eviction_policy=str(getattr(settings, "CACHE_EVICTION_POLICY", "adaptive")).lower(),
            enable_compression=bool(getattr(settings, "CACHE_COMPRESSION_ENABLED", True)),
            compression_threshold=int(getattr(settings, "CACHE_COMPRESSION_THRESHOLD", 2048)),
            auto_tune=bool(getattr(settings, "CACHE_AUTO_TUNE_ENABLED", True)),
            min_cache_size=int(min_size) if min_size is not None else None,
            max_cache_size_limit=int(max_limit) if max_limit is not None else None,
            tune_request_interval=int(getattr(settings, "CACHE_TUNE_REQUEST_INTERVAL", 200)),
        )


class CacheService:
    """缓存服务"""

    def __init__(
        self,
        backend: CacheBackend = None,
        max_size: int = 1000,
        *,
        shard_count: int = 1,
        eviction_policy: str = "adaptive",
        enable_compression: bool = True,
        compression_threshold: int = 2048,
        auto_tune: bool = True,
        min_cache_size: Optional[int] = None,
        max_cache_size_limit: Optional[int] = None,
        tune_request_interval: int = 200
    ):
        self.backend = backend or MemoryCacheBackend()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0,
            'compressions': 0,
            'compression_saved_bytes': 0,
            'auto_tune_adjustments': 0
        }
        self.max_size = max(1, int(max_size))
        self.shard_count = max(1, int(shard_count))
        self.eviction_policy = eviction_policy if eviction_policy in {"lru", "lfu", "adaptive"} else "adaptive"
        self.enable_compression = bool(enable_compression)
        self.compression_threshold = max(128, int(compression_threshold))
        self.auto_tune = bool(auto_tune)
        self.min_cache_size = max(1, int(min_cache_size)) if min_cache_size is not None else max(100, self.max_size // 2)
        configured_max_limit = max_cache_size_limit if max_cache_size_limit is not None else self.max_size * 8
        self.max_cache_size_limit = max(self.max_size, int(configured_max_limit))
        self.tune_request_interval = max(1, int(tune_request_interval))
        self.lock = threading.Lock()
        self._known_keys: set[str] = set()
        self._access_count: Dict[str, int] = {}
        self._last_access_time: Dict[str, float] = {}
        self._key_versions: Dict[str, int] = {}
        self._last_tuned_requests: int = 0

    def generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
        return hashlib.md5(data.encode()).hexdigest()

    def get_shard_for_key(self, key: str) -> int:
        """返回缓存键分片编号"""
        if self.shard_count <= 1:
            return 0
        digest = hashlib.md5(str(key).encode()).hexdigest()
        return int(digest, 16) % self.shard_count

    def resolve_storage_key(self, key: str) -> str:
        """生成后端实际存储键（包含分片前缀）"""
        if self.shard_count <= 1:
            return key
        shard_id = self.get_shard_for_key(key)
        return f"s{shard_id}:{key}"

    def _to_external_key(self, storage_key: str) -> str:
        if self.shard_count <= 1:
            return storage_key
        match = re.match(r"^s\d+:(.*)$", storage_key)
        if match:
            return match.group(1)
        return storage_key

    def _track_access(self, storage_key: str):
        now = time.time()
        self._last_access_time[storage_key] = now
        self._access_count[storage_key] = self._access_count.get(storage_key, 0) + 1

    def _remove_metadata(self, storage_key: str):
        self._known_keys.discard(storage_key)
        self._access_count.pop(storage_key, None)
        self._last_access_time.pop(storage_key, None)
        self._key_versions.pop(storage_key, None)

    def _match_pattern(self, text: str, pattern: str) -> bool:
        if not pattern:
            return True
        if pattern in text:
            return True
        if any(token in pattern for token in ("*", "?", "[", "]")) and fnmatch.fnmatch(text, pattern):
            return True
        try:
            return re.search(pattern, text) is not None
        except re.error:
            return False

    def _encode_value(self, value: Any) -> tuple[Any, int]:
        if not self.enable_compression:
            return value, 0

        try:
            raw_text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return value, 0

        raw_bytes = raw_text.encode("utf-8")
        if len(raw_bytes) < self.compression_threshold:
            return value, 0

        compressed = zlib.compress(raw_bytes, level=6)
        # 仅在收益足够时压缩，避免小对象膨胀
        if len(compressed) + 64 >= len(raw_bytes):
            return value, 0

        envelope = {
            _CACHE_ENVELOPE_KEY: {
                "compressed": True,
                "format": _CACHE_ENVELOPE_FORMAT,
                "raw_size": len(raw_bytes),
                "compressed_size": len(compressed),
            },
            "payload": base64.b64encode(compressed).decode("ascii"),
        }
        return envelope, len(raw_bytes) - len(compressed)

    def _decode_value(self, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        meta = value.get(_CACHE_ENVELOPE_KEY)
        if not isinstance(meta, dict):
            return value
        if not meta.get("compressed") or meta.get("format") != _CACHE_ENVELOPE_FORMAT:
            return value

        payload = value.get("payload")
        if not isinstance(payload, str):
            return value

        try:
            decompressed = zlib.decompress(base64.b64decode(payload.encode("ascii"))).decode("utf-8")
            return json.loads(decompressed)
        except Exception:
            # 解压失败视为损坏数据，返回原值避免影响主流程
            return value

    def _select_eviction_key(self, exclude_key: Optional[str] = None) -> Optional[str]:
        candidates = [key for key in self._known_keys if key != exclude_key]
        if not candidates:
            return None

        total = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total if total > 0 else 0.0
        policy = self.eviction_policy
        if policy == "adaptive":
            policy = "lfu" if hit_rate < 0.6 else "lru"

        if policy == "lfu":
            return min(
                candidates,
                key=lambda key: (self._access_count.get(key, 0), self._last_access_time.get(key, 0.0))
            )
        return min(candidates, key=lambda key: self._last_access_time.get(key, 0.0))

    async def _evict_if_needed(self, incoming_key: str):
        if await self.backend.exists(incoming_key):
            return

        while await self.backend.get_size() >= self.max_size:
            with self.lock:
                victim = self._select_eviction_key(exclude_key=incoming_key)
            if victim is None:
                break
            await self.backend.delete(victim)
            with self.lock:
                self.stats['evictions'] += 1
                self._remove_metadata(victim)

    async def _maybe_auto_tune(self):
        if not self.auto_tune:
            return

        with self.lock:
            total = self.stats['hits'] + self.stats['misses']
            if total == 0 or total % self.tune_request_interval != 0:
                return
            if total == self._last_tuned_requests:
                return
            self._last_tuned_requests = total
            hit_rate = self.stats['hits'] / total if total > 0 else 0.0

        size = await self.backend.get_size()
        usage = size / self.max_size if self.max_size > 0 else 0.0
        new_size = self.max_size

        if hit_rate < 0.55 and usage > 0.85:
            new_size = min(self.max_cache_size_limit, max(self.max_size + 1, int(self.max_size * 1.2)))
        elif hit_rate > 0.9 and usage < 0.4:
            new_size = max(self.min_cache_size, int(self.max_size * 0.9))

        if new_size != self.max_size:
            with self.lock:
                self.max_size = new_size
                self.stats['auto_tune_adjustments'] += 1

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        storage_key = self.resolve_storage_key(key)
        value = await self.backend.get(storage_key)
        decoded = self._decode_value(value) if value is not None else None
        with self.lock:
            if decoded is not None:
                self.stats['hits'] += 1
                self._known_keys.add(storage_key)
                self._track_access(storage_key)
            else:
                self.stats['misses'] += 1
                self._remove_metadata(storage_key)
        await self._maybe_auto_tune()
        return decoded

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None,
        *,
        expected_version: Optional[int] = None
    ) -> int:
        """设置缓存"""
        storage_key = self.resolve_storage_key(key)
        with self.lock:
            if expected_version is not None:
                current = self._key_versions.get(storage_key, 0)
                if current != expected_version:
                    raise ValueError(f"缓存版本不匹配: expected={expected_version}, current={current}")

        encoded_value, saved_bytes = self._encode_value(value)
        await self._evict_if_needed(storage_key)
        await self.backend.set(storage_key, encoded_value, ttl)

        with self.lock:
            self.stats['sets'] += 1
            if saved_bytes > 0:
                self.stats['compressions'] += 1
                self.stats['compression_saved_bytes'] += saved_bytes
            self._known_keys.add(storage_key)
            self._track_access(storage_key)
            self._key_versions[storage_key] = self._key_versions.get(storage_key, 0) + 1
            version = self._key_versions[storage_key]
        await self._maybe_auto_tune()
        return version

    async def delete(self, key: str):
        """删除缓存"""
        storage_key = self.resolve_storage_key(key)
        await self.backend.delete(storage_key)
        with self.lock:
            self.stats['deletes'] += 1
            self._remove_metadata(storage_key)

    async def clear(self):
        """清空缓存"""
        await self.backend.clear()
        with self.lock:
            self.stats = {
                'hits': 0,
                'misses': 0,
                'sets': 0,
                'deletes': 0,
                'evictions': 0,
                'compressions': 0,
                'compression_saved_bytes': 0,
                'auto_tune_adjustments': 0
            }
            self._known_keys.clear()
            self._access_count.clear()
            self._last_access_time.clear()
            self._key_versions.clear()
            self._last_tuned_requests = 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        storage_key = self.resolve_storage_key(key)
        existed = await self.backend.exists(storage_key)
        if not existed:
            with self.lock:
                self._remove_metadata(storage_key)
        return existed

    async def get_size(self) -> int:
        """获取缓存大小"""
        return await self.backend.get_size()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            total = self.stats['hits'] + self.stats['misses']
            shard_distribution: Dict[str, int] = {}
            if self.shard_count > 1:
                for index in range(self.shard_count):
                    shard_distribution[str(index)] = 0
                for storage_key in self._known_keys:
                    match = re.match(r"^s(\d+):", storage_key)
                    if match:
                        shard_distribution[match.group(1)] = shard_distribution.get(match.group(1), 0) + 1
            tracked_size = len(self._known_keys)
            return {
                **self.stats,
                'hit_rate': self.stats['hits'] / total if total > 0 else 0,
                'total_requests': total,
                'tracked_size': tracked_size,
                'usage_rate': tracked_size / self.max_size if self.max_size > 0 else 0,
                'max_size': self.max_size,
                'shard_count': self.shard_count,
                'eviction_policy': self.eviction_policy,
                'compression_enabled': self.enable_compression,
                'compression_threshold': self.compression_threshold,
                'shards': shard_distribution
            }

    def reset_stats(self):
        """重置统计信息"""
        with self.lock:
            self.stats = {
                'hits': 0,
                'misses': 0,
                'sets': 0,
                'deletes': 0,
                'evictions': 0,
                'compressions': 0,
                'compression_saved_bytes': 0,
                'auto_tune_adjustments': 0
            }
            self._last_tuned_requests = 0

    def get_version(self, key: str) -> int:
        """获取缓存键版本号"""
        storage_key = self.resolve_storage_key(key)
        with self.lock:
            return self._key_versions.get(storage_key, 0)

    async def get_with_metadata(self, key: str) -> Dict[str, Any]:
        """获取缓存值及元数据"""
        value = await self.get(key)
        storage_key = self.resolve_storage_key(key)
        with self.lock:
            return {
                "key": key,
                "storage_key": storage_key,
                "shard_id": self.get_shard_for_key(key),
                "version": self._key_versions.get(storage_key, 0),
                "cached": value is not None,
                "value": value
            }

    async def get_monitoring_metrics(self) -> Dict[str, Any]:
        """获取监控指标（用于仪表板和自动调优）"""
        metrics = self.get_stats()
        actual_size = await self.backend.get_size()
        actual_usage_rate = actual_size / self.max_size if self.max_size > 0 else 0.0
        recommendations: List[str] = []

        if metrics['hit_rate'] < 0.5:
            recommendations.append("命中率偏低，建议增加预热任务或延长热点键TTL")
        if actual_usage_rate > 0.9:
            recommendations.append("容量使用率过高，建议扩容或收紧缓存范围")
        if metrics['evictions'] > max(1, metrics['hits']) * 0.3:
            recommendations.append("淘汰频繁，建议切换LFU或提升最大容量")
        if metrics['compressions'] == 0 and self.enable_compression:
            recommendations.append("未触发压缩，可降低压缩阈值以节省内存")

        metrics.update({
            "actual_size": actual_size,
            "actual_usage_rate": actual_usage_rate,
            "recommendations": recommendations
        })
        return metrics

    async def get_or_set(self, key: str, factory: Callable, ttl: int = None) -> Any:
        """获取或设置缓存"""
        value = await self.get(key)
        if value is None:
            value = await factory()
            await self.set(key, value, ttl)
        return value

    async def get_many(self, keys: list) -> Dict[str, Any]:
        """批量获取"""
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def set_many(self, items: Dict[str, Any], ttl: int = None):
        """批量设置"""
        for key, value in items.items():
            await self.set(key, value, ttl)

    async def delete_many(self, keys: list):
        """批量删除"""
        for key in keys:
            await self.delete(key)

    async def invalidate_pattern(self, pattern: str):
        """失效匹配模式的缓存"""
        keys = await self.backend.keys("*")
        for storage_key in keys:
            external_key = self._to_external_key(storage_key)
            if self._match_pattern(external_key, pattern) or self._match_pattern(storage_key, pattern):
                await self.backend.delete(storage_key)
                with self.lock:
                    self.stats['deletes'] += 1
                    self._remove_metadata(storage_key)

    async def export_snapshot(self, pattern: str = "*") -> Dict[str, Any]:
        """导出缓存快照（用于备份）"""
        snapshot: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "items": {}
        }

        for storage_key in await self.backend.keys("*"):
            external_key = self._to_external_key(storage_key)
            if not self._match_pattern(external_key, pattern):
                continue
            raw_value = await self.backend.get(storage_key)
            if raw_value is None:
                continue
            snapshot["items"][external_key] = self._decode_value(raw_value)
        return snapshot

    async def restore_snapshot(self, snapshot: Dict[str, Any], ttl: int = None, clear_first: bool = False):
        """恢复缓存快照（用于故障恢复）"""
        if clear_first:
            await self.clear()
        items = snapshot.get("items", {})
        if not isinstance(items, dict):
            return
        for key, value in items.items():
            await self.set(str(key), value, ttl=ttl)


# 全局缓存服务实例
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """获取全局缓存服务实例"""
    global _cache_service
    if _cache_service is None:
        from ..config import settings
        config = CacheServiceConfig.from_settings(settings)
        if settings.REDIS_ENABLED:
            try:
                redis_backend = RedisCacheBackend(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB
                )
                backend = MultiLevelCacheBackend(
                    l1_backend=MemoryCacheBackend(),
                    l2_backend=redis_backend
                )
            except Exception:
                print("[缓存服务] Redis不可用，使用内存缓存")
                backend = MemoryCacheBackend()
        else:
            backend = MemoryCacheBackend()

        _cache_service = CacheService(
            backend=backend,
            max_size=config.max_size,
            shard_count=config.shard_count,
            eviction_policy=config.eviction_policy,
            enable_compression=config.enable_compression,
            compression_threshold=config.compression_threshold,
            auto_tune=config.auto_tune,
            min_cache_size=config.min_cache_size,
            max_cache_size_limit=config.max_cache_size_limit,
            tune_request_interval=config.tune_request_interval,
        )
    return _cache_service


def reset_cache_service():
    """重置全局缓存服务实例"""
    global _cache_service
    if _cache_service is not None:
        asyncio.create_task(_cache_service.clear())
        _cache_service = None


# 装饰器：缓存函数结果
def cached(ttl: int = 300, key_prefix: str = ""):
    """缓存装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache_service = get_cache_service()

            # 生成缓存键
            cache_key = f"{key_prefix}{cache_service.generate_key(func.__name__, args, kwargs)}"

            # 尝试从缓存获取
            cached_value = await cache_service.get(cache_key)
            if cached_value is not None:
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 缓存结果
            await cache_service.set(cache_key, result, ttl)

            return result
        return wrapper
    return decorator
