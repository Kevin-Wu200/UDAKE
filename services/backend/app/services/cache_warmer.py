"""
缓存预热和失效策略
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .cache_service import CacheService, get_cache_service

logger = logging.getLogger(__name__)


class CacheWarmupTask:
    """缓存预热任务"""

    def __init__(
        self,
        name: str,
        factory: Callable,
        key: str,
        ttl: int = 3600,
        priority: int = 0,
        enabled: bool = True
    ):
        self.name = name
        self.factory = factory
        self.key = key
        self.ttl = ttl
        self.priority = priority  # 优先级，数字越大优先级越高
        self.enabled = enabled
        self.last_warmed: Optional[datetime] = None
        self.last_error: Optional[str] = None


class CacheWarmer:
    """缓存预热器"""

    def __init__(self, cache_service: CacheService = None):
        self.cache_service = cache_service or get_cache_service()
        self.warmup_tasks: Dict[str, CacheWarmupTask] = {}
        self.is_running = False
        self.auto_warmup_interval: int = 3600  # 1小时
        self.auto_warmup_task: Optional[asyncio.Task] = None

    def register_task(
        self,
        name: str,
        factory: Callable,
        key: str,
        ttl: int = 3600,
        priority: int = 0,
        enabled: bool = True
    ):
        """注册预热任务"""
        task = CacheWarmupTask(name, factory, key, ttl, priority, enabled)
        self.warmup_tasks[name] = task
        logger.info(f"[缓存预热] 已注册任务: {name}")

    def unregister_task(self, name: str):
        """注销预热任务"""
        if name in self.warmup_tasks:
            del self.warmup_tasks[name]
            logger.info(f"[缓存预热] 已注销任务: {name}")

    def enable_task(self, name: str):
        """启用预热任务"""
        if name in self.warmup_tasks:
            self.warmup_tasks[name].enabled = True

    def disable_task(self, name: str):
        """禁用预热任务"""
        if name in self.warmup_tasks:
            self.warmup_tasks[name].enabled = False

    async def warmup_task(self, name: str) -> bool:
        """预热单个任务"""
        if name not in self.warmup_tasks:
            logger.warning(f"[缓存预热] 任务不存在: {name}")
            return False

        task = self.warmup_tasks[name]

        if not task.enabled:
            logger.debug(f"[缓存预热] 任务已禁用: {name}")
            return False

        try:
            logger.info(f"[缓存预热] 开始预热任务: {name}")

            # 执行工厂函数获取数据
            value = await task.factory()

            # 缓存数据
            await self.cache_service.set(task.key, value, task.ttl)

            # 更新任务状态
            task.last_warmed = datetime.now()
            task.last_error = None

            logger.info(f"[缓存预热] 预热任务完成: {name}")
            return True

        except Exception as e:
            logger.error(f"[缓存预热] 预热任务失败: {name}, 错误: {e}")
            task.last_error = str(e)
            return False

    async def warmup_all(self, priority_only: bool = False) -> Dict[str, bool]:
        """预热所有任务"""
        if not self.warmup_tasks:
            logger.info("[缓存预热] 没有可预热的任务")
            return {}

        logger.info(f"[缓存预热] 开始预热 {len(self.warmup_tasks)} 个任务...")

        # 按优先级排序
        tasks = sorted(
            self.warmup_tasks.values(),
            key=lambda t: t.priority,
            reverse=True
        )

        results = {}

        for task in tasks:
            if priority_only and task.priority == 0:
                continue

            result = await self.warmup_task(task.name)
            results[task.name] = result

        # 打印摘要
        success_count = sum(1 for r in results.values() if r)
        logger.info(f"[缓存预热] 预热完成: {success_count}/{len(results)} 成功")

        return results

    async def warmup_by_pattern(self, pattern: str) -> Dict[str, bool]:
        """预热匹配模式的任务"""
        matched_tasks = {
            name: task
            for name, task in self.warmup_tasks.items()
            if pattern in name or pattern in task.key
        }

        if not matched_tasks:
            logger.info(f"[缓存预热] 没有匹配模式的任务: {pattern}")
            return {}

        logger.info(f"[缓存预热] 开始预热匹配模式的任务: {pattern} ({len(matched_tasks)} 个)")

        results = {}
        for name, task in matched_tasks.items():
            result = await self.warmup_task(name)
            results[name] = result

        return results

    async def start_auto_warmup(self, interval: int = 3600):
        """启动自动预热"""
        if self.auto_warmup_task is not None:
            logger.warning("[缓存预热] 自动预热已在运行")
            return

        self.auto_warmup_interval = interval
        self.is_running = True
        logger.info(f"[缓存预热] 启动自动预热，间隔: {interval}秒")

        async def _auto_warmup_loop():
            while self.is_running:
                try:
                    await asyncio.sleep(interval)
                    await self.warmup_all()
                except Exception as e:
                    logger.error(f"[缓存预热] 自动预热失败: {e}")

        self.auto_warmup_task = asyncio.create_task(_auto_warmup_loop())

    async def stop_auto_warmup(self):
        """停止自动预热"""
        if self.auto_warmup_task is not None:
            self.is_running = False
            self.auto_warmup_task.cancel()
            try:
                await self.auto_warmup_task
            except asyncio.CancelledError:
                pass
            self.auto_warmup_task = None
            logger.info("[缓存预热] 已停止自动预热")

    def get_task_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        if name not in self.warmup_tasks:
            return None

        task = self.warmup_tasks[name]
        return {
            'name': task.name,
            'key': task.key,
            'ttl': task.ttl,
            'priority': task.priority,
            'enabled': task.enabled,
            'last_warmed': task.last_warmed.isoformat() if task.last_warmed else None,
            'last_error': task.last_error,
            'is_cached': asyncio.create_task(self.cache_service.exists(task.key))
        }

    def get_all_tasks_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态"""
        return {
            name: self.get_task_status(name)
            for name in self.warmup_tasks.keys()
        }


class CacheInvalidator:
    """缓存失效器"""

    def __init__(self, cache_service: CacheService = None):
        self.cache_service = cache_service or get_cache_service()
        self.invalidation_rules: Dict[str, Callable] = {}

    def register_rule(self, name: str, pattern: str, callback: Callable = None):
        """注册失效规则"""
        self.invalidation_rules[name] = {
            'pattern': pattern,
            'callback': callback
        }
        logger.info(f"[缓存失效] 已注册规则: {name} (模式: {pattern})")

    def unregister_rule(self, name: str):
        """注销失效规则"""
        if name in self.invalidation_rules:
            del self.invalidation_rules[name]
            logger.info(f"[缓存失效] 已注销规则: {name}")

    async def invalidate_by_pattern(self, pattern: str):
        """根据模式失效缓存"""
        logger.info(f"[缓存失效] 失效缓存: {pattern}")
        await self.cache_service.invalidate_pattern(pattern)

    async def invalidate_by_rule(self, name: str, *args, **kwargs):
        """根据规则失效缓存"""
        if name not in self.invalidation_rules:
            logger.warning(f"[缓存失效] 规则不存在: {name}")
            return

        rule = self.invalidation_rules[name]

        # 失效匹配的缓存
        await self.invalidate_by_pattern(rule['pattern'])

        # 执行回调
        if rule['callback']:
            try:
                await rule['callback'](*args, **kwargs)
            except Exception as e:
                logger.error(f"[缓存失效] 回调执行失败: {e}")

    async def invalidate_all(self):
        """失效所有缓存"""
        logger.info("[缓存失效] 失效所有缓存")
        await self.cache_service.clear()

    async def invalidate_keys(self, keys: List[str]):
        """失效指定的键"""
        logger.info(f"[缓存失效] 失效 {len(keys)} 个键")
        await self.cache_service.delete_many(keys)

    def get_rules(self) -> Dict[str, str]:
        """获取所有规则"""
        return {
            name: rule['pattern']
            for name, rule in self.invalidation_rules.items()
        }


# 全局实例
_cache_warmer: Optional[CacheWarmer] = None
_cache_invalidator: Optional[CacheInvalidator] = None


def get_cache_warmer() -> CacheWarmer:
    """获取全局缓存预热器实例"""
    global _cache_warmer
    if _cache_warmer is None:
        _cache_warmer = CacheWarmer()
    return _cache_warmer


def get_cache_invalidator() -> CacheInvalidator:
    """获取全局缓存失效器实例"""
    global _cache_invalidator
    if _cache_invalidator is None:
        _cache_invalidator = CacheInvalidator()
    return _cache_invalidator


def reset_cache_warmer():
    """重置全局缓存预热器实例"""
    global _cache_warmer
    if _cache_warmer is not None:
        asyncio.create_task(_cache_warmer.stop_auto_warmup())
        _cache_warmer = None


def reset_cache_invalidator():
    """重置全局缓存失效器实例"""
    global _cache_invalidator
    _cache_invalidator = None
