"""
实时插值系统
Real-time Interpolation System

增量式实时插值功能，支持新数据到达时快速更新插值结果
"""

__version__ = "1.0.0"
__author__ = "UDAKE Team"

# Models
# API
from .api import DataValidator, RealtimeInterpolationService, ServiceManager

# Cache
from .cache import (
    CacheManager,
    CachePreWarmer,
    DistributedCacheManager,
    MultiLevelCacheStrategy,
    RedisCacheManager,
)

# Config
from .config import KrigingConfig

# Core
from .core import (
    BatchUpdateManager,
    BlockMatrixUpdater,
    IncrementalKriging,
    IncrementalSTKriging,
    MultiScaleUpdater,
    ShermanMorrisonUpdater,
    SparseMatrixUpdater,
    ThrottleController,
    UpdatePriorityManager,
    WoodburyUpdater,
)

# Events
from .events import (
    Event,
    EventBus,
    EventMonitor,
    EventPriority,
    EventType,
    RealtimeNotifier,
)

# Index
from .index import GridIndex, KDTree, QuadTree, RTree
from .models import BoundingBox, DataPoint, Subscription, UpdateResult, VariogramModel

__all__ = [
    # Models
    "DataPoint",
    "BoundingBox",
    "Subscription",
    "UpdateResult",
    "VariogramModel",

    # Config
    "KrigingConfig",

    # Core
    "IncrementalKriging",
    "IncrementalSTKriging",
    "ShermanMorrisonUpdater",
    "WoodburyUpdater",
    "BlockMatrixUpdater",
    "SparseMatrixUpdater",
    "MultiScaleUpdater",
    "UpdatePriorityManager",
    "BatchUpdateManager",
    "ThrottleController",

    # Cache
    "CacheManager",
    "DistributedCacheManager",
    "RedisCacheManager",
    "MultiLevelCacheStrategy",
    "CachePreWarmer",

    # Index
    "QuadTree",
    "KDTree",
    "RTree",
    "GridIndex",

    # Events
    "EventBus",
    "EventType",
    "EventPriority",
    "Event",
    "RealtimeNotifier",
    "EventMonitor",

    # API
    "DataValidator",
    "RealtimeInterpolationService",
    "ServiceManager",
]
