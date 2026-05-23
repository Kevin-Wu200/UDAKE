"""
路径规划API接口
提供路径规划的REST API服务
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from ..route_planning.models import (
    OptimizationGoal,
    RoutePlanningRequest,
    RoutePlanningResponse,
    RouteTemplate,
    SamplingPoint,
)
from ..route_planning.services import RouteOptimizer, RoutePlanningService

router = APIRouter(prefix="/api/route-planning", tags=["路径规划"])

# 全局服务实例
route_planning_service = RoutePlanningService()
route_optimizer = RouteOptimizer()

# 存储路径模板
route_templates: Dict[str, RouteTemplate] = {}


@router.post("/plan", response_model=RoutePlanningResponse)
async def plan_route(request: RoutePlanningRequest):
    """
    执行路径规划

    Args:
        request: 路径规划请求

    Returns:
        路径规划响应
    """
    try:
        response = route_planning_service.plan_route(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"路径规划失败：{str(e)}")


@router.post("/optimize")
async def optimize_route(route: Dict[str, Any],
                        optimization_goal: str = "shortest_distance"):
    """
    优化现有路径

    Args:
        route: 路径数据
        optimization_goal: 优化目标

    Returns:
        优化后的路径
    """
    try:
        # 转换为路径对象
        from ..route_planning.models import PlannedRoute, RouteSegment

        point_sequence = route.get("point_sequence", [])
        segments_data = route.get("segments", [])

        segments = []
        for seg_data in segments_data:
            segment = RouteSegment(**seg_data)
            segments.append(segment)

        planned_route = PlannedRoute(
            route_id=route.get("route_id", ""),
            point_sequence=point_sequence,
            segments=segments,
            total_distance=route.get("total_distance", 0),
            total_duration=route.get("total_duration", 0),
            total_cost=route.get("total_cost", 0),
            start_time=datetime.fromisoformat(route["start_time"]) if route.get("start_time") else None,
            end_time=datetime.fromisoformat(route["end_time"]) if route.get("end_time") else None
        )

        # 采样点字典
        sampling_points = {}
        for point_data in route.get("sampling_points", []):
            sampling_point = SamplingPoint(**point_data)
            sampling_points[sampling_point.id] = sampling_point

        # 执行优化
        goal = OptimizationGoal(optimization_goal)
        optimized_route = route_optimizer.optimize_route(
            planned_route,
            sampling_points,
            goal
        )

        # 转换为字典返回
        return optimized_route.dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"路径优化失败：{str(e)}")


@router.post("/add-point")
async def add_point_to_route(route: Dict[str, Any],
                            new_point_data: Dict[str, Any],
                            insert_position: Optional[int] = None):
    """
    向路径中添加新采样点

    Args:
        route: 路径数据
        new_point_data: 新采样点数据
        insert_position: 插入位置

    Returns:
        添加新点后的路径
    """
    try:
        from ..route_planning.models import PlannedRoute, RouteSegment

        # 转换为路径对象
        segments = []
        for seg_data in route.get("segments", []):
            segment = RouteSegment(**seg_data)
            segments.append(segment)

        planned_route = PlannedRoute(
            route_id=route.get("route_id", ""),
            point_sequence=route.get("point_sequence", []),
            segments=segments,
            total_distance=route.get("total_distance", 0),
            total_duration=route.get("total_duration", 0),
            total_cost=route.get("total_cost", 0),
            start_time=datetime.fromisoformat(route["start_time"]) if route.get("start_time") else None,
            end_time=datetime.fromisoformat(route["end_time"]) if route.get("end_time") else None
        )

        # 新采样点
        new_point = SamplingPoint(**new_point_data)

        # 采样点字典
        sampling_points = {}
        for point_data in route.get("sampling_points", []):
            sampling_point = SamplingPoint(**point_data)
            sampling_points[sampling_point.id] = sampling_point

        # 添加新点
        new_route = route_optimizer.add_point_to_route(
            planned_route,
            new_point,
            sampling_points,
            insert_position
        )

        return new_route.dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加采样点失败：{str(e)}")


@router.post("/remove-point")
async def remove_point_from_route(route: Dict[str, Any], point_id: str):
    """
    从路径中移除采样点

    Args:
        route: 路径数据
        point_id: 要移除的点ID

    Returns:
        移除后的路径
    """
    try:
        from ..route_planning.models import PlannedRoute, RouteSegment

        # 转换为路径对象
        segments = []
        for seg_data in route.get("segments", []):
            segment = RouteSegment(**seg_data)
            segments.append(segment)

        planned_route = PlannedRoute(
            route_id=route.get("route_id", ""),
            point_sequence=route.get("point_sequence", []),
            segments=segments,
            total_distance=route.get("total_distance", 0),
            total_duration=route.get("total_duration", 0),
            total_cost=route.get("total_cost", 0),
            start_time=datetime.fromisoformat(route["start_time"]) if route.get("start_time") else None,
            end_time=datetime.fromisoformat(route["end_time"]) if route.get("end_time") else None
        )

        # 采样点字典
        sampling_points = {}
        for point_data in route.get("sampling_points", []):
            sampling_point = SamplingPoint(**point_data)
            sampling_points[sampling_point.id] = sampling_point

        # 移除点
        new_route = route_optimizer.remove_point_from_route(
            planned_route,
            point_id,
            sampling_points
        )

        if new_route is None:
            raise HTTPException(status_code=404, detail=f"采样点{point_id}不存在")

        return new_route.dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移除采样点失败：{str(e)}")


@router.post("/reorder")
async def reorder_route(route: Dict[str, Any],
                        optimization_goal: str = "shortest_distance"):
    """
    重新排序路径中的采样点

    Args:
        route: 路径数据
        optimization_goal: 优化目标

    Returns:
        重新排序后的路径
    """
    try:
        from ..route_planning.models import PlannedRoute, RouteSegment

        # 转换为路径对象
        segments = []
        for seg_data in route.get("segments", []):
            segment = RouteSegment(**seg_data)
            segments.append(segment)

        planned_route = PlannedRoute(
            route_id=route.get("route_id", ""),
            point_sequence=route.get("point_sequence", []),
            segments=segments,
            total_distance=route.get("total_distance", 0),
            total_duration=route.get("total_duration", 0),
            total_cost=route.get("total_cost", 0),
            start_time=datetime.fromisoformat(route["start_time"]) if route.get("start_time") else None,
            end_time=datetime.fromisoformat(route["end_time"]) if route.get("end_time") else None
        )

        # 采样点字典
        sampling_points = {}
        for point_data in route.get("sampling_points", []):
            sampling_point = SamplingPoint(**point_data)
            sampling_points[sampling_point.id] = sampling_point

        # 重新排序
        goal = OptimizationGoal(optimization_goal)
        new_route = route_optimizer.reorder_route(
            planned_route,
            sampling_points,
            goal
        )

        return new_route.dict()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新排序失败：{str(e)}")


@router.post("/templates")
async def create_route_template(template_data: Dict[str, Any]):
    """
    创建路径模板

    Args:
        template_data: 模板数据

    Returns:
        创建的模板
    """
    try:
        template = RouteTemplate(**template_data)
        route_templates[template.template_id] = template
        return template.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建模板失败：{str(e)}")


@router.get("/templates")
async def get_route_templates():
    """
    获取所有路径模板

    Returns:
        模板列表
    """
    return list(route_templates.values())


@router.get("/templates/{template_id}")
async def get_route_template(template_id: str):
    """
    获取指定路径模板

    Args:
        template_id: 模板ID

    Returns:
        模板数据
    """
    template = route_templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"模板{template_id}不存在")
    return template.dict()


@router.delete("/templates/{template_id}")
async def delete_route_template(template_id: str):
    """
    删除路径模板

    Args:
        template_id: 模板ID

    Returns:
        删除结果
    """
    if template_id not in route_templates:
        raise HTTPException(status_code=404, detail=f"模板{template_id}不存在")

    del route_templates[template_id]
    return {"message": f"模板{template_id}已删除"}


@router.get("/algorithms")
async def get_available_algorithms():
    """
    获取可用的路径规划算法

    Returns:
        算法列表
    """
    algorithms = [
        {
            "id": "auto",
            "name": "自动选择",
            "description": "根据采样点数量自动选择最优算法"
        },
        {
            "id": "dijkstra",
            "name": "Dijkstra算法",
            "description": "经典最短路径算法，适合小规模问题"
        },
        {
            "id": "astar",
            "name": "A*算法",
            "description": "启发式搜索算法，适合带目标点的问题"
        },
        {
            "id": "tsp",
            "name": "TSP算法",
            "description": "旅行商问题求解算法，包含最近邻、2-opt、模拟退火等"
        },
        {
            "id": "aco",
            "name": "蚁群算法",
            "description": "基于蚂蚁觅食行为的元启发式算法，适合大规模问题"
        }
    ]

    return algorithms


@router.get("/vehicle-types")
async def get_vehicle_types():
    """
    获取支持的车辆类型

    Returns:
        车辆类型列表
    """
    return [
        {
            "id": "car",
            "name": "轿车",
            "description": "标准车辆，速度适中"
        },
        {
            "id": "suv",
            "name": "SUV",
            "description": "运动型多用途车，适合越野"
        },
        {
            "id": "truck",
            "name": "卡车",
            "description": "大型车辆，速度较慢但载重大"
        },
        {
            "id": "walking",
            "name": "步行",
            "description": "步行采样"
        }
    ]


@router.get("/optimization-goals")
async def get_optimization_goals():
    """
    获取支持的优化目标

    Returns:
        优化目标列表
    """
    return [
        {
            "id": "shortest_distance",
            "name": "最短距离",
            "description": "优化路径总距离"
        },
        {
            "id": "shortest_time",
            "name": "最短时间",
            "description": "优化路径总时间"
        },
        {
            "id": "lowest_cost",
            "name": "最低成本",
            "description": "优化路径总成本"
        },
        {
            "id": "balanced",
            "name": "综合优化",
            "description": "综合考虑距离、时间和成本"
        }
    ]


@router.post("/validate")
async def validate_route(route: Dict[str, Any], constraints: Dict[str, Any]):
    """
    验证路径是否满足约束条件

    Args:
        route: 路径数据
        constraints: 约束条件

    Returns:
        验证结果
    """
    try:
        from ..route_planning.models import PlannedRoute, RouteConstraint, RouteSegment

        # 转换为路径对象
        segments = []
        for seg_data in route.get("segments", []):
            segment = RouteSegment(**seg_data)
            segments.append(segment)

        planned_route = PlannedRoute(
            route_id=route.get("route_id", ""),
            point_sequence=route.get("point_sequence", []),
            segments=segments,
            total_distance=route.get("total_distance", 0),
            total_duration=route.get("total_duration", 0),
            total_cost=route.get("total_cost", 0),
            start_time=datetime.fromisoformat(route["start_time"]) if route.get("start_time") else None,
            end_time=datetime.fromisoformat(route["end_time"]) if route.get("end_time") else None
        )

        # 采样点字典
        sampling_points = {}
        for point_data in route.get("sampling_points", []):
            sampling_point = SamplingPoint(**point_data)
            sampling_points[sampling_point.id] = sampling_point

        # 约束条件
        constraint_obj = RouteConstraint(**constraints)

        # 验证
        from ..route_planning.utils import check_all_constraints
        is_valid, details = check_all_constraints(
            planned_route,
            sampling_points,
            constraint_obj
        )

        return {
            "is_valid": is_valid,
            "details": details
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败：{str(e)}")
