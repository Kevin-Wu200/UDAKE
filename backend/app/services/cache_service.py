"""
缓存服务
支持内存缓存和Redis缓存
"""

from typing import Any, Optional, Dict, Callable
import json
import hashlib
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import asyncio
import threading


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


class CacheService:
    """缓存服务"""

    def __init__(self, backend: CacheBackend = None, max_size: int = 1000):
        self.backend = backend or MemoryCacheBackend()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
        self.max_size = max_size
        self.lock = threading.Lock()

    def generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
        return hashlib.md5(data.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        value = await self.backend.get(key)
        with self.lock:
            if value is not None:
                self.stats['hits'] += 1
            else:
                self.stats['misses'] += 1
        return value

    async def set(self, key: str, value: Any, ttl: int = None):
        """设置缓存"""
        with self.lock:
            self.stats['sets'] += 1
        await self.backend.set(key, value, ttl)

    async def delete(self, key: str):
        """删除缓存"""
        with self.lock:
            self.stats['deletes'] += 1
        await self.backend.delete(key)

    async def clear(self):
        """清空缓存"""
        await self.backend.clear()
        with self.lock:
            self.stats = {
                'hits': 0,
                'misses': 0,
                'sets': 0,
                'deletes': 0
            }

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return await self.backend.exists(key)

    async def get_size(self) -> int:
        """获取缓存大小"""
        return await self.backend.get_size()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            total = self.stats['hits'] + self.stats['misses']
            return {
                **self.stats,
                'hit_rate': self.stats['hits'] / total if total > 0 else 0,
                'total_requests': total
            }

    def reset_stats(self):
        """重置统计信息"""
        with self.lock:
            self.stats = {
                'hits': 0,
                'misses': 0,
                'sets': 0,
                'deletes': 0
            }

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
        # 这里简化处理，实际应用中可能需要更复杂的模式匹配
        if isinstance(self.backend, MemoryCacheBackend):
            with self.backend.lock:
                keys_to_delete = [
                    key for key in self.backend.cache.keys()
                    if pattern in key
                ]
                for key in keys_to_delete:
                    del self.backend.cache[key]
        elif isinstance(self.backend, RedisCacheBackend):
            # Redis支持SCAN命令进行模式匹配
            loop = asyncio.get_event_loop()
            for key in await loop.run_in_executor(
                None,
                lambda: self.backend.client.scan_iter(match=pattern)
            ):
                await self.delete(key)


# 全局缓存服务实例
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """获取全局缓存服务实例"""
    global _cache_service
    if _cache_service is None:
        from ..config import settings
        if settings.REDIS_ENABLED:
            try:
                backend = RedisCacheBackend(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB
                )
            except Exception:
                print("[缓存服务] Redis不可用，使用内存缓存")
                backend = MemoryCacheBackend()
        else:
            backend = MemoryCacheBackend()

        _cache_service = CacheService(
            backend=backend,
            max_size=settings.CACHE_MAX_SIZE if hasattr(settings, 'CACHE_MAX_SIZE') else 1000
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