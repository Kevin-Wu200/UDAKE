"""
多目标优化系统 FastAPI 路由
Multi-Objective Optimization System API Routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ..core.optimizer import BaseOptimizer
from ..core.nsga2 import NSGA2Optimizer
from ..core.population import Population, Individual
from ..objectives.variance import VarianceObjective
from ..objectives.cost import CostObjective
from ..objectives.accessibility import AccessibilityObjective
from ..constraints.boundary import BoundaryConstraint
from ..constraints.distance import DistanceConstraint
from ..constraints.budget import BudgetConstraint

router = APIRouter()

# 任务存储（内存中，生产环境应使用数据库）
tasks_db = {}


# ==================== 数据模型 ====================

class OptimizationRequest(BaseModel):
    """优化请求"""
    variance_grid: Dict[str, Any]
    existing_points: List[Dict[str, float]]
    n_samples: int
    weights: Dict[str, float]
    constraints: Dict[str, Any]
    algorithm: str = "NSGA-II"
    algorithm_params: Optional[Dict[str, Any]] = None
    is_async: bool = True


class OptimizationResponse(BaseModel):
    """优化响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str
    request_id: str


# ==================== 优化任务接口 ====================

@router.post("/multi-objective/optimize", response_model=OptimizationResponse)
async def create_optimization_task(request: OptimizationRequest):
    """
    创建并执行多目标优化任务
    """
    try:
        task_id = f"task_{int(datetime.now().timestamp() * 1000)}"

        # 提取variance_grid数据
        variance_grid_data = request.variance_grid
        if isinstance(variance_grid_data, dict):
            variance_grid_array = np.array(variance_grid_data.get('data', []))
            bounds = variance_grid_data.get('bounds', {})
            x_coords = np.array([bounds.get('minX', 0.0), bounds.get('maxX', 1.0)])
            y_coords = np.array([bounds.get('minY', 0.0), bounds.get('maxY', 1.0)])
        else:
            # 如果是列表格式，尝试转换
            variance_grid_array = np.array(variance_grid_data)
            x_coords = np.array([0.0, 1.0])
            y_coords = np.array([0.0, 1.0])

        # 创建目标函数
        objectives = [
            VarianceObjective(
                variance_grid=variance_grid_array,
                x_coords=x_coords,
                y_coords=y_coords,
                weight=request.weights.get('variance', 0.5)
            ),
            CostObjective(weight=request.weights.get('cost', 0.3)),
            AccessibilityObjective(weight=request.weights.get('accessibility', 0.2))
        ]

        # 创建约束
        constraints = []

        if 'boundary' in request.constraints:
            boundary = request.constraints['boundary']
            # 转换边界格式：字典 -> 坐标点列表
            if isinstance(boundary, dict):
                # 假设字典包含minX, minY, maxX, maxY
                min_x = boundary.get('minX', 0.0)
                min_y = boundary.get('minY', 0.0)
                max_x = boundary.get('maxX', 1.0)
                max_y = boundary.get('maxY', 1.0)
                boundary_points = [
                    [min_x, min_y],
                    [max_x, min_y],
                    [max_x, max_y],
                    [min_x, max_y],
                    [min_x, min_y]  # 闭合多边形
                ]
                constraints.append(BoundaryConstraint(boundary_points))
            else:
                constraints.append(BoundaryConstraint(boundary))

        if 'min_distance' in request.constraints:
            constraints.append(DistanceConstraint(request.constraints['min_distance']))

        if 'budget' in request.constraints:
            constraints.append(BudgetConstraint(request.constraints['budget']))

        # 创建优化器
        optimizer = NSGA2Optimizer(
            objectives=objectives,
            constraints=constraints,
            n_candidates=request.algorithm_params.get('n_candidates', 1000) if request.algorithm_params else 1000,
            n_samples=request.n_samples
        )

        # 存储任务
        tasks_db[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'input_params': request.dict(),
            'results': None,
            'statistics': None,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None
        }

        return OptimizationResponse(
            success=True,
            message="优化任务已创建",
            data={
                'task_id': task_id,
                'status': 'pending',
                'estimated_time': 8.5,
                'created_at': tasks_db[task_id]['created_at']
            },
            timestamp=datetime.now().isoformat(),
            request_id=task_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建优化任务失败: {str(e)}")


@router.get("/multi-objective/tasks/{task_id}/status", response_model=OptimizationResponse)
async def get_task_status(task_id: str):
    """
    查询优化任务状态
    """
    try:
        if task_id not in tasks_db:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = tasks_db[task_id]

        return OptimizationResponse(
            success=True,
            message="查询成功",
            data={
                'task_id': task['task_id'],
                'status': task['status'],
                'progress': 100 if task['status'] == 'completed' else 0,
                'current_generation': 0,
                'total_generations': 100,
                'elapsed_time': 0,
                'estimated_remaining_time': 0,
                'started_at': task.get('started_at'),
                'updated_at': task.get('updated_at')
            },
            timestamp=datetime.now().isoformat(),
            request_id=task_id
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")


@router.get("/multi-objective/tasks/{task_id}", response_model=OptimizationResponse)
async def get_task_info(task_id: str):
    """
    获取优化任务信息
    """
    try:
        if task_id not in tasks_db:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = tasks_db[task_id]

        return OptimizationResponse(
            success=True,
            message="查询成功",
            data={
                'task_id': task['task_id'],
                'status': task['status'],
                'input_params': task.get('input_params', {}),
                'results': task.get('results'),
                'statistics': task.get('statistics'),
                'created_at': task.get('created_at'),
                'started_at': task.get('started_at'),
                'completed_at': task.get('completed_at')
            },
            timestamp=datetime.now().isoformat(),
            request_id=task_id
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务信息失败: {str(e)}")


@router.get("/multi-objective/tasks/{task_id}/results", response_model=OptimizationResponse)
async def get_task_results(task_id: str, format: str = "detailed"):
    """
    获取优化任务结果
    """
    try:
        if task_id not in tasks_db:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = tasks_db[task_id]

        if task['status'] != 'completed':
            raise HTTPException(status_code=400, detail="任务尚未完成")

        return OptimizationResponse(
            success=True,
            message="获取成功",
            data=task.get('results', {}),
            timestamp=datetime.now().isoformat(),
            request_id=task_id
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务结果失败: {str(e)}")


@router.delete("/multi-objective/tasks/{task_id}", response_model=OptimizationResponse)
async def cancel_task(task_id: str):
    """
    取消正在运行的优化任务
    """
    try:
        if task_id not in tasks_db:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = tasks_db[task_id]

        if task['status'] == 'completed':
            raise HTTPException(status_code=400, detail="任务已完成")

        task['status'] = 'cancelled'
        task['cancelled_at'] = datetime.now().isoformat()

        return OptimizationResponse(
            success=True,
            message="任务已取消",
            data={
                'task_id': task_id,
                'status': 'cancelled',
                'cancelled_at': task['cancelled_at']
            },
            timestamp=datetime.now().isoformat(),
            request_id=task_id
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")


# ==================== 配置管理接口 ====================

@router.get("/multi-objective/config", response_model=OptimizationResponse)
async def get_config():
    """
    获取系统配置
    """
    try:
        config = {
            'algorithms': {
                'NSGA-II': {
                    'name': 'Non-dominated Sorting Genetic Algorithm II',
                    'description': '基于非支配排序的多目标进化算法',
                    'default_params': {
                        'population_size': 100,
                        'n_generations': 100,
                        'crossover_prob': 0.9,
                        'mutation_prob': 0.1
                    },
                    'supported': True
                }
            },
            'objectives': {
                'variance': {
                    'name': '方差最小化',
                    'description': '最小化插值预测方差',
                    'direction': 'minimize',
                    'default_weight': 0.5
                },
                'cost': {
                    'name': '成本最小化',
                    'description': '最小化采样总成本',
                    'direction': 'minimize',
                    'default_weight': 0.3
                },
                'accessibility': {
                    'name': '可达性最大化',
                    'description': '最大化采样点可达性',
                    'direction': 'maximize',
                    'default_weight': 0.2
                }
            },
            'constraints': {
                'boundary': {
                    'name': '边界约束',
                    'description': '限制采样点在指定边界内',
                    'type': 'geometry'
                },
                'min_distance': {
                    'name': '最小间距约束',
                    'description': '限制采样点最小间距',
                    'type': 'numeric',
                    'default_value': 50
                },
                'budget': {
                    'name': '预算约束',
                    'description': '限制采样总成本',
                    'type': 'numeric'
                }
            },
            'limits': {
                'max_samples': 1000,
                'max_candidates': 10000,
                'max_generations': 500,
                'max_population_size': 500
            }
        }

        return OptimizationResponse(
            success=True,
            message="获取成功",
            data=config,
            timestamp=datetime.now().isoformat(),
            request_id="config"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


# ==================== 历史任务接口 ====================

@router.get("/multi-objective/tasks", response_model=OptimizationResponse)
async def list_tasks(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    获取用户的优化任务列表
    """
    try:
        # 过滤任务
        filtered_tasks = []
        for task_id, task in tasks_db.items():
            if status and task['status'] != status:
                continue
            filtered_tasks.append({
                'task_id': task_id,
                'status': task['status'],
                'n_samples': task['input_params'].get('n_samples', 0),
                'algorithm': task['input_params'].get('algorithm', 'NSGA-II'),
                'created_at': task['created_at'],
                'completed_at': task.get('completed_at'),
                'total_time': 0
            })

        # 分页
        total = len(filtered_tasks)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        tasks = filtered_tasks[start_idx:end_idx]

        return OptimizationResponse(
            success=True,
            message="获取成功",
            data={
                'tasks': tasks,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size
                }
            },
            timestamp=datetime.now().isoformat(),
            request_id=f"list_tasks_{page}"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


# ==================== 结果导出接口 ====================

@router.get("/multi-objective/tasks/{task_id}/export/geojson", response_model=OptimizationResponse)
async def export_geojson(task_id: str, solution_id: Optional[int] = None):
    """
    导出优化结果为GeoJSON格式
    """
    try:
        if task_id not in tasks_db:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = tasks_db[task_id]

        if task['status'] != 'completed':
            raise HTTPException(status_code=400, detail="任务尚未完成")

        # 简化导出逻辑
        result = {
            'type': 'FeatureCollection',
            'crs': {
                'type': 'name',
                'properties': {'name': 'EPSG:4326'}
            },
            'features': []
        }

        return OptimizationResponse(
            success=True,
            message="导出成功",
            data=result,
            timestamp=datetime.now().isoformat(),
            request_id=task_id
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出GeoJSON失败: {str(e)}")


# ==================== 系统状态接口 ====================

@router.get("/multi-objective/status", response_model=OptimizationResponse)
async def get_optimization_status():
    """
    获取多目标优化系统状态

    返回多目标优化系统的整体状态信息，包括：
    - 活跃任务数
    - 完成任务数
    - 系统健康状态
    - 可用算法和目标函数
    """
    try:
        # 获取任务统计信息
        all_tasks = list(tasks_db.values())
        active_tasks = [t for t in all_tasks if t.get('status') in ['pending', 'running']]
        completed_tasks = [t for t in all_tasks if t.get('status') == 'completed']

        # 可用算法
        available_algorithms = [
            {"id": "NSGA-II", "name": "非支配排序遗传算法 II", "description": "基于非支配排序的多目标进化算法"}
        ]

        # 可用目标函数
        available_objectives = [
            {"id": "variance", "name": "方差最小化", "description": "最小化插值预测方差"},
            {"id": "cost", "name": "成本最小化", "description": "最小化采样总成本"},
            {"id": "accessibility", "name": "可达性最大化", "description": "最大化采样点可达性"}
        ]

        # 可用约束
        available_constraints = [
            {"id": "boundary", "name": "边界约束", "description": "限制采样点在指定边界内"},
            {"id": "min_distance", "name": "最小间距约束", "description": "限制采样点最小间距"},
            {"id": "budget", "name": "预算约束", "description": "限制采样总成本"}
        ]

        status_data = {
            "system": "healthy",
            "active_tasks": len(active_tasks),
            "completed_tasks": len(completed_tasks),
            "total_tasks": len(all_tasks),
            "available_algorithms": available_algorithms,
            "available_objectives": available_objectives,
            "available_constraints": available_constraints
        }

        return OptimizationResponse(
            success=True,
            message="获取状态成功",
            data=status_data,
            timestamp=datetime.now().isoformat(),
            request_id="system_status"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")