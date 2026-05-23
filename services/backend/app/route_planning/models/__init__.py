"""
路径规划数据模型
定义采样路径规划系统中的数据结构
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VehicleType(str, Enum):
    """车辆类型"""
    CAR = "car"
    TRUCK = "truck"
    SUV = "suv"
    WALKING = "walking"


class OptimizationGoal(str, Enum):
    """优化目标"""
    SHORTEST_DISTANCE = "shortest_distance"
    SHORTEST_TIME = "shortest_time"
    LOWEST_COST = "lowest_cost"
    BALANCED = "balanced"


class SamplingPoint(BaseModel):
    """采样点模型"""
    id: str = Field(..., description="采样点ID")
    name: Optional[str] = Field(None, description="采样点名称")
    latitude: float = Field(..., description="纬度", ge=-90, le=90)
    longitude: float = Field(..., description="经度", ge=-180, le=180)
    priority: int = Field(1, description="优先级 (1-10)", ge=1, le=10)
    time_window_start: Optional[str] = Field(None, description="时间窗开始 (HH:MM)")
    time_window_end: Optional[str] = Field(None, description="时间窗结束 (HH:MM)")
    service_time: int = Field(10, description="服务时间（分钟）", ge=0)
    is_reachable: bool = Field(True, description="是否可达")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class RouteSegment(BaseModel):
    """路径段模型"""
    from_point_id: str = Field(..., description="起点ID")
    to_point_id: str = Field(..., description="终点ID")
    distance: float = Field(..., description="距离（米）")
    duration: float = Field(..., description="时间（秒）")
    cost: float = Field(..., description="成本")
    geometry: Optional[Dict[str, Any]] = Field(None, description="路径几何信息")
    instructions: Optional[List[str]] = Field(None, description="导航指引")


class PlannedRoute(BaseModel):
    """规划路径模型"""
    route_id: str = Field(..., description="路径ID")
    point_sequence: List[str] = Field(..., description="采样点访问顺序")
    segments: List[RouteSegment] = Field(..., description="路径段列表")
    total_distance: float = Field(..., description="总距离（米）")
    total_duration: float = Field(..., description="总时间（秒）")
    total_cost: float = Field(..., description="总成本")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")


class RouteConstraint(BaseModel):
    """路径约束条件"""
    max_distance: Optional[float] = Field(None, description="最大距离（米）")
    max_duration: Optional[float] = Field(None, description="最大时间（秒）")
    max_cost: Optional[float] = Field(None, description="最大成本")
    time_windows: bool = Field(False, description="是否考虑时间窗")
    priority_constraint: bool = Field(False, description="是否考虑优先级")
    vehicle_type: VehicleType = Field(VehicleType.CAR, description="车辆类型")
    max_load: Optional[float] = Field(None, description="最大载重")


class RoutePlanningRequest(BaseModel):
    """路径规划请求模型"""
    sampling_points: List[SamplingPoint] = Field(..., description="采样点列表")
    start_point: SamplingPoint = Field(..., description="起点")
    end_point: Optional[SamplingPoint] = Field(None, description="终点（可选）")
    constraints: RouteConstraint = Field(default_factory=RouteConstraint, description="约束条件")
    optimization_goal: OptimizationGoal = Field(OptimizationGoal.SHORTEST_DISTANCE, description="优化目标")
    algorithm: str = Field("auto", description="算法选择 (auto/dijkstra/astar/tsp/aco)")
    return_multiple_routes: bool = Field(False, description="是否返回多个路径方案")


class RoutePlanningResponse(BaseModel):
    """路径规划响应模型"""
    success: bool = Field(..., description="是否成功")
    routes: List[PlannedRoute] = Field(..., description="规划路径列表")
    best_route: Optional[PlannedRoute] = Field(None, description="最优路径")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="统计信息")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    computation_time: float = Field(..., description="计算时间（秒）")


class RouteTemplate(BaseModel):
    """路径模板模型"""
    template_id: str = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    sampling_points: List[SamplingPoint] = Field(..., description="采样点列表")
    constraints: RouteConstraint = Field(..., description="约束条件")
    optimization_goal: OptimizationGoal = Field(..., description="优化目标")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
