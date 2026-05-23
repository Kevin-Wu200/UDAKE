"""
核心模块
Core Module

导出核心功能
"""

from .matrix_update import (
    ShermanMorrisonUpdater,
    WoodburyUpdater,
    BlockMatrixUpdater,
    SparseMatrixUpdater
)

from .incremental_kriging import IncrementalKriging
from .incremental_st_kriging import IncrementalSTKriging
from .co_kriging import CoKriging, CrossVariogramModel
from .kriging_accelerator import (
    QuadTreeLOD,
    build_covariance_matrix_fast,
    build_covariance_vector_fast,
    predict_kriging_fast,
    compute_covariance_fast,
    predict_grid_parallel,
    model_type_to_enum,
    VARIOGRAM_SPHERICAL,
    VARIOGRAM_EXPONENTIAL,
    VARIOGRAM_GAUSSIAN,
    VARIOGRAM_POWER,
    VARIOGRAM_LINEAR,
    VARIOGRAM_LOGARITHMIC,
)

from .update_strategy import (
    UpdatePriority,
    UpdateScale,
    UpdateTask,
    MultiScaleUpdater,
    UpdatePriorityManager,
    BatchUpdateManager,
    ThrottleController
)

__all__ = [
    # Matrix Update
    'ShermanMorrisonUpdater',
    'WoodburyUpdater',
    'BlockMatrixUpdater',
    'SparseMatrixUpdater',

    # Incremental Kriging
    'IncrementalKriging',
    'IncrementalSTKriging',
    'CoKriging',
    'CrossVariogramModel',

    # Performance Acceleration
    'QuadTreeLOD',
    'build_covariance_matrix_fast',
    'build_covariance_vector_fast',
    'predict_kriging_fast',
    'compute_covariance_fast',
    'predict_grid_parallel',
    'model_type_to_enum',
    'VARIOGRAM_SPHERICAL',
    'VARIOGRAM_EXPONENTIAL',
    'VARIOGRAM_GAUSSIAN',
    'VARIOGRAM_POWER',
    'VARIOGRAM_LINEAR',
    'VARIOGRAM_LOGARITHMIC',

    # Update Strategy
    'UpdatePriority',
    'UpdateScale',
    'UpdateTask',
    'MultiScaleUpdater',
    'UpdatePriorityManager',
    'BatchUpdateManager',
    'ThrottleController',
]
