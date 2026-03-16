"""
实时插值系统配置文件
Real-time Interpolation System Configuration
"""

from typing import Dict, Any
from dataclasses import dataclass, field
import os


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

        # 从环境变量覆盖配置
        if os.getenv("REDIS_HOST"):
            config.cache.l2_host = os.getenv("REDIS_HOST")
        if os.getenv("REDIS_PORT"):
            config.cache.l2_port = int(os.getenv("REDIS_PORT"))
        if os.getenv("LOG_LEVEL"):
            config.logging.level = os.getenv("LOG_LEVEL")
        if os.getenv("MAX_MEMORY_GB"):
            config.performance.max_memory_usage_gb = float(os.getenv("MAX_MEMORY_GB"))

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