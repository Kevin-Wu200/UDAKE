"""
实时插值系统配置文件
Real-time Interpolation System Configuration
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import os
from pathlib import Path


_DOTENV_CACHE: Optional[Dict[str, str]] = None


def _load_dotenv_fallback() -> Dict[str, str]:
    global _DOTENV_CACHE
    if _DOTENV_CACHE is not None:
        return _DOTENV_CACHE
    env_file = Path(__file__).resolve().parents[1] / "configs" / "env" / ".env"
    parsed: Dict[str, str] = {}
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            parsed[key.strip()] = value.strip()
    _DOTENV_CACHE = parsed
    return parsed


def _get_env_value(key: str) -> Optional[str]:
    value = os.getenv(key)
    if value is not None:
        return value
    return _load_dotenv_fallback().get(key)


@dataclass
class CacheConfig:
    """缓存配置"""
    # L1缓存（内存）
    l1_capacity: int = 1000  # 最大缓存项数
    l1_ttl: int = 300  # 默认过期时间（秒）

    # L2缓存（Redis）
    l2_enabled: bool = True
    l2_host: str = "localhost"
    l2_port: int = 6379
    l2_db: int = 0
    l2_password: str = ""
    l2_url: str = ""
    l2_pool_size: int = 20
    l2_timeout: int = 5
    l2_retry_times: int = 3
    l2_strict: bool = False
    l2_ttl: int = 3600  # 默认过期时间（秒）

    # L3缓存（磁盘）
    l3_enabled: bool = True
    l3_path: str = "/tmp/realtime_interpolation_cache"
    l3_ttl: int = 86400  # 默认过期时间（秒）

    # 替换策略
    replacement_strategy: str = "lfu"  # lru, lfu, arc


@dataclass
class KrigingConfig:
    """克里金插值配置"""
    # 默认参数
    default_method: str = "ordinary_kriging"
    default_variogram_model: str = "spherical"

    # 增量更新
    enable_incremental: bool = True
    max_updates_before_recalc: int = 100  # 最大更新次数后重计算

    # 批量更新
    batch_size: int = 10  # 批量大小
    batch_timeout: float = 1.0  # 批量超时时间（秒）

    # 影响域
    influence_radius_multiplier: float = 2.0  # 影响半径乘数
    min_influence_radius: float = 10.0  # 最小影响半径
    max_influence_radius: float = 1000.0  # 最大影响半径

    # 数值精度
    epsilon: float = 1e-10  # 数值稳定性阈值
    precision: float = 1e-6  # 计算精度


@dataclass
class IndexConfig:
    """空间索引配置"""
    index_type: str = "quadtree"  # quadtree, kdtree, rtree

    # 四叉树配置
    quadtree_max_capacity: int = 10  # 每个节点最大数据点数
    quadtree_max_depth: int = 20  # 最大深度

    # KD树配置
    kdtree_leaf_size: int = 10  # 叶节点大小

    # 网格索引配置
    grid_resolution: int = 100  # 网格分辨率


@dataclass
class EventConfig:
    """事件系统配置"""
    # 事件队列
    event_queue_size: int = 10000  # 事件队列大小

    # WebSocket
    websocket_enabled: bool = True
    websocket_host: str = "0.0.0.0"
    websocket_port: int = 8001

    # Server-Sent Events
    sse_enabled: bool = True

    # 事件持久化
    enable_persistence: bool = False
    persistence_path: str = "/tmp/realtime_interpolation_events"


@dataclass
class PerformanceConfig:
    """性能配置"""
    # 并发
    max_concurrent_updates: int = 100  # 最大并发更新数
    thread_pool_size: int = 10  # 线程池大小

    # 内存
    max_memory_usage_gb: float = 10.0  # 最大内存使用（GB）

    # 监控
    enable_monitoring: bool = True
    monitoring_interval: int = 60  # 监控间隔（秒）


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "/tmp/realtime_interpolation.log"
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5


@dataclass
class Config:
    """实时插值系统总配置"""

    cache: CacheConfig = field(default_factory=CacheConfig)
    kriging: KrigingConfig = field(default_factory=KrigingConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    events: EventConfig = field(default_factory=EventConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        config = cls()

        redis_enabled_env = _get_env_value("REDIS_ENABLED")
        if redis_enabled_env is not None:
            redis_enabled = redis_enabled_env.strip().lower() in {"1", "true", "yes", "on"}
            config.cache.l2_enabled = redis_enabled
            if not redis_enabled:
                config.cache.l2_url = ""
                config.cache.l2_host = ""

        # 从环境变量覆盖配置
        redis_host = _get_env_value("REDIS_HOST")
        redis_port = _get_env_value("REDIS_PORT")
        redis_db = _get_env_value("REDIS_DB")
        redis_password = _get_env_value("REDIS_PASSWORD")
        redis_url = _get_env_value("REDIS_URL")
        redis_pool_size = _get_env_value("REDIS_POOL_SIZE")
        redis_timeout = _get_env_value("REDIS_TIMEOUT")
        redis_retry_times = _get_env_value("REDIS_RETRY_TIMES")
        redis_strict = _get_env_value("REDIS_STRICT")
        log_level = _get_env_value("LOG_LEVEL")
        max_memory_gb = _get_env_value("MAX_MEMORY_GB")

        if config.cache.l2_enabled and redis_host:
            config.cache.l2_host = redis_host
        if config.cache.l2_enabled and redis_port:
            config.cache.l2_port = int(redis_port)
        if config.cache.l2_enabled and redis_db:
            config.cache.l2_db = int(redis_db)
        if config.cache.l2_enabled and redis_password:
            config.cache.l2_password = redis_password
        if config.cache.l2_enabled and redis_url:
            config.cache.l2_url = redis_url
        if config.cache.l2_enabled and redis_pool_size:
            config.cache.l2_pool_size = int(redis_pool_size)
        if config.cache.l2_enabled and redis_timeout:
            config.cache.l2_timeout = int(redis_timeout)
        if config.cache.l2_enabled and redis_retry_times:
            config.cache.l2_retry_times = int(redis_retry_times)
        if config.cache.l2_enabled and redis_strict:
            config.cache.l2_strict = redis_strict.strip().lower() in {"1", "true", "yes", "on"}
        if log_level:
            config.logging.level = log_level
        if max_memory_gb:
            config.performance.max_memory_usage_gb = float(max_memory_gb)

        return config

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "cache": self.cache.__dict__,
            "kriging": self.kriging.__dict__,
            "index": self.index.__dict__,
            "events": self.events.__dict__,
            "performance": self.performance.__dict__,
            "logging": self.logging.__dict__,
        }


# 全局配置实例
global_config = Config.from_env()


def get_config() -> Config:
    """获取全局配置"""
    return global_config


def update_config(**kwargs) -> None:
    """更新全局配置"""
    for key, value in kwargs.items():
        if hasattr(global_config, key):
            setattr(global_config, key, value)
