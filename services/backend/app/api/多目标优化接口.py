"""
多目标优化采样接口
Multi-Objective Optimization Sampling API
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
from fastapi import APIRouter, BackgroundTasks, HTTPException

from multi_objective_optimization import (
    AccessibilityObjective,
    BoundaryConstraint,
    BudgetConstraint,
    CostObjective,
    DistanceConstraint,
    NSGA2Optimizer,
    TimeWindowConstraint,
    VarianceObjective,
)
from multi_objective_optimization.utils.metrics import calculate_performance_metrics

from ..dependencies import verify_task_id
from ..tasks.任务管理器 import TaskManager

logger = logging.getLogger(__name__)

router = APIRouter()
task_manager = TaskManager()

# 存储优化任务的字典
optimization_tasks: Dict[str, Dict[str, Any]] = {}


class OptimizationRequest:
    """优化请求模型"""
    def __init__(
        self,
        task_id: str,
        variance_grid: Dict[str, Any],
        n_samples: int = 20,
        weights: Dict[str, float] = None,
        constraints: Dict[str, Any] = None,
        algorithm: str = "NSGA-II",
        algorithm_params: Dict[str, Any] = None,
        async_mode: bool = True
    ):
        self.task_id = task_id
        self.variance_grid = variance_grid
        self.n_samples = n_samples
        self.weights = weights or {"variance": 0.5, "cost": 0.3, "accessibility": 0.2}
        self.constraints = constraints or {}
        self.algorithm = algorithm
        self.algorithm_params = algorithm_params or {
            "population_size": 100,
            "n_generations": 100,
            "crossover_prob": 0.9,
            "mutation_prob": 0.1
        }
        self.async_mode = async_mode


@router.post("/multi-objective/optimize")
async def create_optimization_task(
    task_id: str,
    variance_grid: Dict[str, Any],
    n_samples: int = 20,
    weights: Dict[str, float] = None,
    constraints: Dict[str, Any] = None,
    algorithm: str = "NSGA-II",
    algorithm_params: Dict[str, Any] = None,
    async_mode: bool = True,
    background_tasks: BackgroundTasks = None
):
    """
    创建并执行多目标优化任务

    参数:
    - task_id: 任务ID
    - variance_grid: 方差网格数据
      - shape: 网格形状 [height, width]
      - x_coords: X坐标数组
      - y_coords: Y坐标数组
      - values: 方差值二维数组
    - n_samples: 采样点数量
    - weights: 目标权重
      - variance: 方差权重
      - cost: 成本权重
      - accessibility: 可达性权重
    - constraints: 约束条件
      - boundary: 边界多边形坐标
      - min_distance: 最小间距
      - budget: 预算限制
    - algorithm: 优化算法（NSGA-II或MOEA/D）
    - algorithm_params: 算法参数
      - population_size: 种群规模
      - n_generations: 进化代数
      - crossover_prob: 交叉概率
      - mutation_prob: 变异概率
    - async_mode: 是否异步执行
    """
    try:
        # 验证任务
        verify_task_id(task_id)

        # 验证输入参数
        if "values" not in variance_grid or "x_coords" not in variance_grid or "y_coords" not in variance_grid:
            raise HTTPException(status_code=400, detail="方差网格数据不完整")

        # 生成优化任务ID
        opt_task_id = f"opt_{uuid.uuid4().hex}"

        # 创建任务记录
        optimization_tasks[opt_task_id] = {
            "task_id": opt_task_id,
            "parent_task_id": task_id,
            "status": "pending",
            "created_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "input_params": {
                "variance_grid": variance_grid,
                "n_samples": n_samples,
                "weights": weights,
                "constraints": constraints,
                "algorithm": algorithm,
                "algorithm_params": algorithm_params
            },
            "results": None,
            "error": None
        }

        if async_mode:
            # 异步执行优化
            if background_tasks:
                background_tasks.add_task(
                    run_optimization_async,
                    opt_task_id,
                    variance_grid,
                    n_samples,
                    weights,
                    constraints,
                    algorithm,
                    algorithm_params
                )
        else:
            # 同步执行优化（快速响应，适用于小规模问题）
            try:
                result = await run_optimization_sync(
                    opt_task_id,
                    variance_grid,
                    n_samples,
                    weights,
                    constraints,
                    algorithm,
                    algorithm_params
                )
                optimization_tasks[opt_task_id]["results"] = result
                optimization_tasks[opt_task_id]["status"] = "completed"
                optimization_tasks[opt_task_id]["completed_at"] = datetime.now()
            except Exception as e:
                logger.error(f"优化任务执行失败: {str(e)}", exc_info=True)
                optimization_tasks[opt_task_id]["status"] = "failed"
                optimization_tasks[opt_task_id]["error"] = str(e)

        return {
            "success": True,
            "message": "优化任务已创建",
            "data": {
                "task_id": opt_task_id,
                "status": "running" if async_mode else "completed",
                "created_at": optimization_tasks[opt_task_id]["created_at"].isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建优化任务失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建优化任务失败: {str(e)}")


async def run_optimization_async(
    opt_task_id: str,
    variance_grid: Dict[str, Any],
    n_samples: int,
    weights: Dict[str, float],
    constraints: Dict[str, Any],
    algorithm: str,
    algorithm_params: Dict[str, Any]
):
    """异步执行优化任务"""
    try:
        optimization_tasks[opt_task_id]["status"] = "running"
        optimization_tasks[opt_task_id]["started_at"] = datetime.now()

        # 在线程池中执行CPU密集型任务
        result = await asyncio.to_thread(
            run_optimization,
            opt_task_id,
            variance_grid,
            n_samples,
            weights,
            constraints,
            algorithm,
            algorithm_params
        )

        optimization_tasks[opt_task_id]["results"] = result
        optimization_tasks[opt_task_id]["status"] = "completed"
        optimization_tasks[opt_task_id]["completed_at"] = datetime.now()

    except Exception as e:
        logger.error(f"异步优化任务执行失败: {str(e)}", exc_info=True)
        optimization_tasks[opt_task_id]["status"] = "failed"
        optimization_tasks[opt_task_id]["error"] = str(e)


async def run_optimization_sync(
    opt_task_id: str,
    variance_grid: Dict[str, Any],
    n_samples: int,
    weights: Dict[str, float],
    constraints: Dict[str, Any],
    algorithm: str,
    algorithm_params: Dict[str, Any]
):
    """同步执行优化任务"""
    return run_optimization(
        opt_task_id,
        variance_grid,
        n_samples,
        weights,
        constraints,
        algorithm,
        algorithm_params
    )


def run_optimization(
    opt_task_id: str,
    variance_grid: Dict[str, Any],
    n_samples: int,
    weights: Dict[str, float],
    constraints: Dict[str, Any],
    algorithm: str,
    algorithm_params: Dict[str, Any]
):
    """执行优化任务（核心逻辑）"""
    # 解析方差网格
    variance_array = np.array(variance_grid["values"])
    x_coords = np.array(variance_grid["x_coords"])
    y_coords = np.array(variance_grid["y_coords"])

    # 创建目标函数
    objectives = [
        VarianceObjective(variance_array, x_coords, y_coords, weight=weights.get("variance", 0.5)),
        CostObjective(base_location=(0, 0), weight=weights.get("cost", 0.3)),
        AccessibilityObjective(base_location=(0, 0), weight=weights.get("accessibility", 0.2))
    ]

    # 创建约束条件
    constraint_list = []

    if "boundary" in constraints:
        boundary_coords = constraints["boundary"]
        boundary_constraint = BoundaryConstraint(boundary_coords, x_coords, y_coords)
        constraint_list.append(boundary_constraint)

    if "min_distance" in constraints:
        min_distance = constraints["min_distance"]
        distance_constraint = DistanceConstraint(min_distance, x_coords, y_coords)
        constraint_list.append(distance_constraint)

    if "budget" in constraints:
        budget = constraints["budget"]
        budget_constraint = BudgetConstraint(budget, base_location=(0, 0))
        constraint_list.append(budget_constraint)

    if "time_window" in constraints:
        tw_config = constraints["time_window"]
        time_window_constraint = TimeWindowConstraint(
            time_windows=tw_config.get("time_windows"),
            max_total_time=tw_config.get("max_total_time", 480.0),
            time_per_sample=tw_config.get("time_per_sample", 15.0),
            travel_speed=tw_config.get("travel_speed", 30.0),
            base_location=tw_config.get("base_location", (0, 0)),
            x_coords=x_coords,
            y_coords=y_coords,
            start_time=tw_config.get("start_time", 0.0),
        )
        constraint_list.append(time_window_constraint)

    # 创建优化器
    n_candidates = len(x_coords) * len(y_coords)

    if algorithm == "NSGA-II":
        optimizer = NSGA2Optimizer(
            objectives=objectives,
            constraints=constraint_list,
            n_candidates=n_candidates,
            n_samples=n_samples,
            random_seed=42
        )
    else:
        raise ValueError(f"不支持的算法: {algorithm}")

    # 运行优化
    result_pop = optimizer.optimize(
        population_size=algorithm_params.get("population_size", 100),
        n_generations=algorithm_params.get("n_generations", 100),
        crossover_prob=algorithm_params.get("crossover_prob", 0.9),
        mutation_prob=algorithm_params.get("mutation_prob", 0.1),
        verbose=False
    )

    # 获取帕累托前沿
    pareto_front = result_pop.get_pareto_front()

    # 构建结果
    pareto_solutions = []
    for idx, individual in enumerate(pareto_front):
        # 将基因索引转换为坐标
        points = []
        for gene_idx in individual.genes:
            row = gene_idx // len(x_coords)
            col = gene_idx % len(x_coords)
            x = x_coords[col] if col < len(x_coords) else 0
            y = y_coords[row] if row < len(y_coords) else 0
            points.append((x, y))

        pareto_solutions.append({
            "id": idx + 1,
            "objectives": {
                "variance": float(individual.objectives[0]),
                "cost": float(individual.objectives[1]),
                "accessibility": float(individual.objectives[2])
            },
            "sampling_points": points,
            "rank": individual.rank,
            "crowding_distance": individual.crowding_distance
        })

    # 获取推荐方案
    weights_array = np.array([
        weights.get("variance", 0.5),
        weights.get("cost", 0.3),
        weights.get("accessibility", 0.2)
    ])
    best_solution = optimizer.get_best_solution(result_pop, weights_array)

    recommended_solution = None
    if best_solution:
        points = []
        for gene_idx in best_solution.genes:
            row = gene_idx // len(x_coords)
            col = gene_idx % len(x_coords)
            x = x_coords[col] if col < len(x_coords) else 0
            y = y_coords[row] if row < len(y_coords) else 0
            points.append((x, y))

        recommended_solution = {
            "id": best_solution.rank,
            "objectives": {
                "variance": float(best_solution.objectives[0]),
                "cost": float(best_solution.objectives[1]),
                "accessibility": float(best_solution.objectives[2])
            },
            "sampling_points": points,
            "rank": best_solution.rank,
            "crowding_distance": best_solution.crowding_distance
        }

    # 计算性能指标
    metrics = calculate_performance_metrics(result_pop)

    return {
        "pareto_solutions": pareto_solutions,
        "recommended_solution": recommended_solution,
        "convergence_history": optimizer.convergence_history,
        "metrics": metrics,
        "statistics": result_pop.get_statistics()
    }


@router.get("/multi-objective/tasks/{opt_task_id}/status")
async def get_optimization_status(opt_task_id: str):
    """
    查询优化任务状态

    参数:
    - opt_task_id: 优化任务ID
    """
    try:
        if opt_task_id not in optimization_tasks:
            raise HTTPException(status_code=404, detail="优化任务不存在")

        task = optimization_tasks[opt_task_id]

        status_info = {
            "task_id": opt_task_id,
            "status": task["status"],
            "created_at": task["created_at"].isoformat(),
            "started_at": task["started_at"].isoformat() if task["started_at"] else None,
            "completed_at": task["completed_at"].isoformat() if task["completed_at"] else None
        }

        if task["status"] == "running" and task["started_at"]:
            elapsed = (datetime.now() - task["started_at"]).total_seconds()
            status_info["elapsed_time"] = elapsed

        return {
            "success": True,
            "message": "查询成功",
            "data": status_info
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务状态失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")


@router.get("/multi-objective/tasks/{opt_task_id}/results")
async def get_optimization_results(opt_task_id: str):
    """
    获取优化任务结果

    参数:
    - opt_task_id: 优化任务ID
    """
    try:
        if opt_task_id not in optimization_tasks:
            raise HTTPException(status_code=404, detail="优化任务不存在")

        task = optimization_tasks[opt_task_id]

        if task["status"] == "pending":
            raise HTTPException(status_code=400, detail="任务尚未开始")
        if task["status"] == "running":
            raise HTTPException(status_code=400, detail="任务正在运行中")
        if task["status"] == "failed":
            error_msg = task.get("error", "未知错误")
            raise HTTPException(status_code=500, detail=f"任务执行失败: {error_msg}")

        return {
            "success": True,
            "message": "获取成功",
            "data": {
                "task_id": opt_task_id,
                "status": task["status"],
                "results": task["results"],
                "completed_at": task["completed_at"].isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取优化结果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取优化结果失败: {str(e)}")


@router.get("/multi-objective/config")
async def get_optimization_config():
    """
    获取系统配置
    """
    try:
        config = {
            "algorithms": {
                "NSGA-II": {
                    "name": "Non-dominated Sorting Genetic Algorithm II",
                    "description": "基于非支配排序的多目标进化算法",
                    "default_params": {
                        "population_size": 100,
                        "n_generations": 100,
                        "crossover_prob": 0.9,
                        "mutation_prob": 0.1
                    },
                    "supported": True
                }
            },
            "objectives": {
                "variance": {
                    "name": "方差最小化",
                    "description": "最小化插值预测方差",
                    "direction": "minimize",
                    "default_weight": 0.5
                },
                "cost": {
                    "name": "成本最小化",
                    "description": "最小化采样总成本",
                    "direction": "minimize",
                    "default_weight": 0.3
                },
                "accessibility": {
                    "name": "可达性最大化",
                    "description": "最大化采样点可达性",
                    "direction": "maximize",
                    "default_weight": 0.2
                }
            },
            "constraints": {
                "boundary": {
                    "name": "边界约束",
                    "description": "限制采样点在指定边界内",
                    "type": "geometry"
                },
                "min_distance": {
                    "name": "最小间距约束",
                    "description": "限制采样点最小间距",
                    "type": "numeric",
                    "default_value": 50
                },
                "time_window": {
                    "name": "时间窗约束",
                    "description": "限制各采样点的采集时间在指定时间窗内",
                    "type": "temporal",
                    "default_max_total_time": 480,
                    "default_time_per_sample": 15,
                    "default_travel_speed": 30
                },
                "budget": {
                    "name": "预算约束",
                    "description": "限制采样总成本",
                    "type": "numeric"
                }
            },
            "limits": {
                "max_samples": 1000,
                "max_candidates": 10000,
                "max_generations": 500,
                "max_population_size": 500
            }
        }

        return {
            "success": True,
            "message": "获取成功",
            "data": config
        }

    except Exception as e:
        logger.error(f"获取配置失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.get("/multi-objective/tasks/{opt_task_id}/export/geojson")
async def export_results_geojson(opt_task_id: str, solution_id: Optional[int] = None):
    """
    导出优化结果为GeoJSON格式

    参数:
    - opt_task_id: 优化任务ID
    - solution_id: 方案ID（可选，默认为推荐方案）
    """
    try:
        if opt_task_id not in optimization_tasks:
            raise HTTPException(status_code=404, detail="优化任务不存在")

        task = optimization_tasks[opt_task_id]

        if task["status"] != "completed":
            raise HTTPException(status_code=400, detail="任务尚未完成")

        results = task["results"]

        # 选择要导出的方案
        if solution_id is None:
            solution = results.get("recommended_solution")
        else:
            pareto_solutions = results.get("pareto_solutions", [])
            solution = next((s for s in pareto_solutions if s["id"] == solution_id), None)

        if not solution:
            raise HTTPException(status_code=404, detail="方案不存在")

        # 转换为GeoJSON
        features = []
        for idx, point in enumerate(solution["sampling_points"]):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [point[0], point[1]]
                },
                "properties": {
                    "id": idx + 1,
                    "solution_id": solution["id"],
                    "objectives": solution["objectives"],
                    "rank": solution["rank"],
                    "crowding_distance": solution["crowding_distance"]
                }
            }
            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": "EPSG:4326"}
            },
            "features": features
        }

        return {
            "success": True,
            "message": "导出成功",
            "data": geojson
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出GeoJSON失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出GeoJSON失败: {str(e)}")
