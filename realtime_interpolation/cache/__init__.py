"""
缓存模块
Cache Module

导出缓存相关功能
"""

from .cache_strategy import (
    CacheLevel,
    ReplacementPolicy,
    CacheEntry,
    CachePolicy,
    MultiLevelCacheStrategy,
    CachePreWarmer
)

from .cache_manager import (
    CacheStats,
    CacheManager,
    DistributedCacheManager
)
from .redis_cache_manager import RedisCacheManager

__all__ = [
    # Cache Strategy
    'CacheLevel',
    'ReplacementPolicy',
    'CacheEntry',
    'CachePolicy',
    'MultiLevelCacheStrategy',
    'CachePreWarmer',

    # Cache Manager
    'CacheStats',
    'CacheManager',
    'DistributedCacheManager',
    'RedisCacheManager',
]
