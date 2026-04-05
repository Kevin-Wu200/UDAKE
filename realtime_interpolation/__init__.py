"""
实时插值系统
Real-time Interpolation System

增量式实时插值功能，支持新数据到达时快速更新插值结果
"""

__version__ = "1.0.0"
__author__ = "UDAKE Team"

# Models
from .models import (
    DataPoint,
    BoundingBox,
    Subscription,
    UpdateResult,
    VariogramModel
)

# Config
from .config import KrigingConfig

# Core
from .core import (
    IncrementalKriging,
    IncrementalSTKriging,
    ShermanMorrisonUpdater,
    WoodburyUpdater,
    BlockMatrixUpdater,
    SparseMatrixUpdater,
    MultiScaleUpdater,
    UpdatePriorityManager,
    BatchUpdateManager,
    ThrottleController
)

# Cache
from .cache import (
    CacheManager,
    DistributedCacheManager,
    RedisCacheManager,
    MultiLevelCacheStrategy,
    CachePreWarmer
)

# Index
from .index import (
    QuadTree,
    KDTree,
    RTree,
    GridIndex
)

# Events
from .events import (
    EventBus,
    EventType,
    EventPriority,
    Event,
    RealtimeNotifier,
    EventMonitor
)

# API
from .api import (
    DataValidator,
    RealtimeInterpolationService,
    ServiceManager
)

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
