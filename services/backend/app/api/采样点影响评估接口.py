"""
采样点影响评估接口
提供候选采样点评估、实时预览、最优推荐和批量模拟功能
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..core.实时采样预览 import RealTimeSamplingPreview
from ..core.改进的采样推荐器 import ImprovedSamplingRecommender
from ..core.采样点影响评估器 import SamplingPointImpactEvaluator
from ..tasks.任务管理器 import TaskManager
from ..utils.栅格工具 import RasterUtils

logger = logging.getLogger(__name__)

router = APIRouter()
task_manager = TaskManager()
raster_utils = RasterUtils()

# 初始化核心算法实例
impact_evaluator = SamplingPointImpactEvaluator(max_workers=4)
sampling_recommender = ImprovedSamplingRecommender(
    impact_evaluator=impact_evaluator,
    max_workers=4
)
sampling_preview = RealTimeSamplingPreview(impact_evaluator=impact_evaluator)


# ==================== 请求/响应模型 ====================

class Point(BaseModel):
    """点坐标"""
    x: float = Field(..., description="X坐标")
    y: float = Field(..., description="Y坐标")
    value: Optional[float] = Field(None, description="值（可选，如果不提供将通过克里金估算）")


class EvaluateCandidatesRequest(BaseModel):
    """评估候选采样点请求"""
    task_id: str = Field(..., description="任务ID")
    candidate_points: List[Point] = Field(..., description="候选采样点列表")
    strategy: str = Field(default="impact_optimized", description="评估策略")
    grid_resolution: int = Field(default=50, description="评估网格分辨率")
    influence_radius: Optional[float] = Field(None, description="影响半径（可选，自动计算）")


class CandidateEvaluationResult(BaseModel):
    """候选点评估结果"""
    candidate_index: int = Field(..., description="候选点索引")
    x: float = Field(..., description="X坐标")
    y: float = Field(..., description="Y坐标")
    variance_reduction: float = Field(..., description="方差减少量")
    variance_reduction_ratio: float = Field(..., description="方差减少比例")
    local_improvement: float = Field(..., description="局部改善度")
    comprehensive_score: float = Field(..., description="综合评分")
    influence_radius: float = Field(..., description="影响半径")
    error: Optional[str] = Field(None, description="错误信息（如果评估失败）")


class EvaluateCandidatesResponse(BaseModel):
    """评估候选采样点响应"""
    task_id: str = Field(..., description="任务ID")
    strategy: str = Field(..., description="使用的策略")
    n_candidates: int = Field(..., description="候选点数量")
    n_evaluated: int = Field(..., description="成功评估的数量")
    results: List[CandidateEvaluationResult] = Field(..., description="评估结果列表")
    summary: Dict[str, Any] = Field(..., description="摘要统计")
    evaluated_at: datetime = Field(..., description="评估时间")


class PreviewEffectRequest(BaseModel):
    """预览采样效果请求"""
    task_id: str = Field(..., description="任务ID")
    new_point: Point = Field(..., description="新采样点")
    grid_resolution: int = Field(default=50, description="预览网格分辨率")


class PreviewEffectResponse(BaseModel):
    """预览采样效果响应"""
    task_id: str = Field(..., description="任务ID")
    new_point: Dict[str, float] = Field(..., description="新采样点信息")
    variance_reduction_map: Dict[str, Any] = Field(..., description="方差减少热力图")
    total_variance_reduction: float = Field(..., description="总方差减少量")
    variance_reduction_ratio: float = Field(..., description="方差减少比例")
    influence_radius: float = Field(..., description="影响半径")
    improved_regions: List[Dict[str, Any]] = Field(..., description="改善区域列表")
    quantitative_metrics: Dict[str, float] = Field(..., description="量化指标")
    previewed_at: datetime = Field(..., description="预览时间")


class RecommendOptimalRequest(BaseModel):
    """推荐最优采样点请求"""
    task_id: str = Field(..., description="任务ID")
    n_recommendations: int = Field(default=20, description="推荐点数量")
    strategy: str = Field(default="impact_optimized", description="推荐策略")
    constraints: Optional[Dict[str, Any]] = Field(None, description="约束条件")


class RecommendOptimalResponse(BaseModel):
    """推荐最优采样点响应"""
    task_id: str = Field(..., description="任务ID")
    strategy: str = Field(..., description="使用的策略")
    n_recommendations: int = Field(..., description="推荐点数量")
    recommendations: List[Dict[str, Any]] = Field(..., description="推荐点列表")
    constraints_applied: Optional[Dict[str, Any]] = Field(None, description="应用的约束条件")
    recommended_at: datetime = Field(..., description="推荐时间")


class SamplingPlan(BaseModel):
    """采样方案"""
    plan_id: str = Field(..., description="方案ID")
    name: str = Field(..., description="方案名称")
    points: List[Point] = Field(..., description="采样点列表")


class BatchSimulateRequest(BaseModel):
    """批量模拟请求"""
    task_id: str = Field(..., description="任务ID")
    sampling_plans: List[SamplingPlan] = Field(..., description="采样方案列表")
    grid_resolution: int = Field(default=50, description="评估网格分辨率")


class SimulationResult(BaseModel):
    """模拟结果"""
    plan_id: str = Field(..., description="方案ID")
    name: str = Field(..., description="方案名称")
    n_points: int = Field(..., description="采样点数量")
    mean_variance: float = Field(..., description="平均方差")
    max_variance: float = Field(..., description="最大方差")
    total_variance_reduction: float = Field(..., description="总方差减少量")
    rmse_improvement: float = Field(..., description="RMSE改善百分比")


class BatchSimulateResponse(BaseModel):
    """批量模拟响应"""
    task_id: str = Field(..., description="任务ID")
    n_plans: int = Field(..., description="方案数量")
    results: List[SimulationResult] = Field(..., description="模拟结果列表")
    comparison: Dict[str, Any] = Field(..., description="方案对比")
    simulated_at: datetime = Field(..., description="模拟时间")


# ==================== 辅助函数 ====================

def _get_task_data(task_id: str):
    """
    获取任务数据

    返回:
    - existing_points: 现有采样点坐标
    - existing_values: 现有采样点值
    - variance_grid: 方差栅格
    - x_coords: X坐标
    - y_coords: Y坐标
    """
    # 读取方差栅格
    variance_path = settings.RESULTS_DIR / f"{task_id}_variance.tif"
    if not variance_path.exists():
        raise HTTPException(status_code=404, detail="方差栅格不存在，请先完成插值计算")

    from osgeo import gdal
    dataset = gdal.Open(str(variance_path))
    if dataset is None:
        raise HTTPException(status_code=500, detail="无法打开方差栅格文件")

    variance = dataset.GetRasterBand(1).ReadAsArray()
    transform = dataset.GetGeoTransform()
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize
    dataset = None

    # 生成坐标网格
    x_coords = np.array([transform[0] + transform[1] * x for x in range(cols)])
    y_coords = np.array([transform[3] + transform[5] * y for y in range(rows)])

    # 获取原始采样点
    existing_points = None
    existing_values = None
    try:
        task_info = task_manager.get_task_info(task_id)
        if task_info and task_info.data_id:
            spatial_data = task_manager.get_spatial_data(task_info.data_id)
            if spatial_data:
                existing_points = np.array([[p.x, p.y] for p in spatial_data.points])
                existing_values = np.array([p.value for p in spatial_data.points])
    except Exception as e:
        logger.warning(f"从TaskManager获取原始采样点失败: {str(e)}")

    # 如果从TaskManager获取失败，尝试从插值结果存储获取
    if existing_points is None:
        try:
            from ..services.插值结果存储 import get_interpolation_storage
            storage = get_interpolation_storage()
            result = storage.get_result(task_id)

            # 从栅格边界生成虚拟点（用于影响评估计算）
            if result:
                grid = np.array(result['grid'])
                grid_shape = grid.shape

                # 使用栅格的几个关键点作为虚拟点，并获取对应的预测值
                # 从grid中提取对应位置的值
                rows, cols = grid_shape

                # 定义关键点位置（左上、右上、左下、右下、中心）
                corner_positions = [
                    (0, 0),  # 左上角
                    (0, cols-1),  # 右上角
                    (rows-1, 0),  # 左下角
                    (rows-1, cols-1),  # 右下角
                    (rows//2, cols//2)  # 中心点
                ]

                existing_points = []
                existing_values = []

                for r, c in corner_positions:
                    existing_points.append([x_coords[c], y_coords[r]])
                    existing_values.append(grid[r, c])

                existing_points = np.array(existing_points)
                existing_values = np.array(existing_values)

                logger.info(f"使用虚拟点进行影响评估: {task_id}, 点数: {len(existing_points)}")
                logger.info(f"虚拟点坐标范围: X[{existing_points[:, 0].min():.6f}, {existing_points[:, 0].max():.6f}], Y[{existing_points[:, 1].min():.6f}, {existing_points[:, 1].max():.6f}]")
                logger.info(f"虚拟点值范围: [{existing_values.min():.6f}, {existing_values.max():.6f}]")
        except Exception as e:
            logger.warning(f"从插值结果存储获取数据失败: {str(e)}")
            logger.warning(f"错误详情: {e}")

    if existing_points is None:
        raise HTTPException(status_code=404, detail="无法获取原始采样点数据")

    return existing_points, existing_values, variance, x_coords, y_coords


# ==================== API接口 ====================

@router.post("/evaluate-candidates", response_model=EvaluateCandidatesResponse)
async def evaluate_candidates(
    request: EvaluateCandidatesRequest,
    background_tasks: BackgroundTasks
):
    """
    评估候选采样点的影响

    评估候选采样点对插值精度的影响，计算方差减少、局部改善等指标。

    性能要求：处理50个候选点响应时间<5秒
    """
    try:
        # 获取任务数据
        existing_points, existing_values, variance, x_coords, y_coords = _get_task_data(request.task_id)

        # 准备候选点数据
        candidate_points = np.array([[p.x, p.y] for p in request.candidate_points])
        candidate_values = None
        if all(p.value is not None for p in request.candidate_points):
            candidate_values = np.array([p.value for p in request.candidate_points])

        # 执行评估
        logger.info(f"开始评估 {len(request.candidate_points)} 个候选点")
        start_time = datetime.now()

        results = impact_evaluator.evaluate_impact(
            existing_points=existing_points,
            existing_values=existing_values,
            candidate_points=candidate_points,
            candidate_values=candidate_values,
            grid_resolution=request.grid_resolution,
            influence_radius=request.influence_radius
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 转换为响应格式
        evaluation_results = []
        for i, result in enumerate(results):
            evaluation_results.append(CandidateEvaluationResult(
                candidate_index=result.get('candidate_index', i),
                x=float(request.candidate_points[i].x),
                y=float(request.candidate_points[i].y),
                variance_reduction=result.get('variance_reduction', 0.0),
                variance_reduction_ratio=result.get('variance_reduction_ratio', 0.0),
                local_improvement=result.get('local_improvement', 0.0),
                comprehensive_score=result.get('comprehensive_score', 0.0),
                influence_radius=result.get('influence_radius', 0.0),
                error=result.get('error')
            ))

        # 计算摘要统计
        n_evaluated = len([r for r in evaluation_results if r.error is None])
        if n_evaluated > 0:
            valid_results = [r for r in evaluation_results if r.error is None]
            summary = {
                "n_evaluated": n_evaluated,
                "n_failed": len(evaluation_results) - n_evaluated,
                "mean_variance_reduction": float(np.mean([r.variance_reduction for r in valid_results])),
                "max_variance_reduction": float(np.max([r.variance_reduction for r in valid_results])),
                "mean_comprehensive_score": float(np.mean([r.comprehensive_score for r in valid_results])),
                "processing_time_seconds": duration
            }
        else:
            summary = {
                "n_evaluated": 0,
                "n_failed": len(evaluation_results),
                "processing_time_seconds": duration
            }

        return EvaluateCandidatesResponse(
            task_id=request.task_id,
            strategy=request.strategy,
            n_candidates=len(request.candidate_points),
            n_evaluated=n_evaluated,
            results=evaluation_results,
            summary=summary,
            evaluated_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"评估候选点失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"评估候选点失败: {str(e)}")


@router.post("/preview-effect", response_model=PreviewEffectResponse)
async def preview_effect(request: PreviewEffectRequest):
    """
    实时预览添加新采样点后的效果

    预览添加新采样点后的方差减少热力图、改善区域和量化指标。

    性能要求：响应时间<3秒
    """
    try:
        # 获取任务数据
        existing_points, existing_values, variance, x_coords, y_coords = _get_task_data(request.task_id)

        # 准备新点数据
        new_point = np.array([request.new_point.x, request.new_point.y])
        new_value = request.new_point.value

        if new_value is None:
            raise HTTPException(status_code=400, detail="新采样点必须提供值")

        # 执行预览
        logger.info(f"预览添加新采样点: ({new_point[0]:.2f}, {new_point[1]:.2f})")
        start_time = datetime.now()

        results = sampling_preview.preview_sampling_effect(
            existing_points=existing_points,
            existing_values=existing_values,
            new_point=new_point,
            new_value=new_value,
            grid_resolution=request.grid_resolution,
            variance_grid=variance,
            x_coords=x_coords,
            y_coords=y_coords
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 添加处理时间到量化指标
        results['quantitative_metrics']['processing_time_seconds'] = duration

        return PreviewEffectResponse(
            task_id=request.task_id,
            new_point={
                "x": float(request.new_point.x),
                "y": float(request.new_point.y),
                "value": float(new_value)
            },
            variance_reduction_map=results['variance_reduction_map'],
            total_variance_reduction=results['total_variance_reduction'],
            variance_reduction_ratio=results['variance_reduction_ratio'],
            influence_radius=results['influence_radius'],
            improved_regions=results['improved_regions'],
            quantitative_metrics=results['quantitative_metrics'],
            previewed_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预览采样效果失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"预览采样效果失败: {str(e)}")


@router.post("/recommend-optimal", response_model=RecommendOptimalResponse)
async def recommend_optimal(request: RecommendOptimalRequest):
    """
    推荐最优采样点

    根据指定的策略推荐最优采样点，支持多种推荐策略和约束条件。

    支持的策略：
    - impact_optimized: 基于影响优化（推荐）
    - variance_based: 基于方差优先
    - spatial_coverage: 基于空间覆盖
    - hybrid: 混合策略

    性能要求：推荐10个点响应时间<10秒
    """
    try:
        # 获取任务数据
        existing_points, existing_values, variance, x_coords, y_coords = _get_task_data(request.task_id)

        # 执行推荐
        logger.info(f"推荐最优采样点，策略: {request.strategy}, 数量: {request.n_recommendations}")
        start_time = datetime.now()  # noqa: F841

        results = sampling_recommender.recommend_optimal_points(
            existing_points=existing_points,
            existing_values=existing_values,
            variance_grid=variance,
            x_coords=x_coords,
            y_coords=y_coords,
            n_recommendations=request.n_recommendations,
            strategy=request.strategy,
            constraints=request.constraints
        )

        end_time = datetime.now()

        return RecommendOptimalResponse(
            task_id=request.task_id,
            strategy=results['strategy'],
            n_recommendations=results['n_recommendations'],
            recommendations=results['recommendations'],
            constraints_applied=results.get('constraints_applied'),
            recommended_at=end_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"推荐最优采样点失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"推荐最优采样点失败: {str(e)}")


@router.post("/batch-simulate", response_model=BatchSimulateResponse)
async def batch_simulate(request: BatchSimulateRequest):
    """
    批量模拟多个采样方案的效果

    对比不同采样方案的效果，返回各方案的详细结果和对比分析。

    用途：对比不同采样策略的效果
    """
    try:
        # 获取任务数据
        existing_points, existing_values, variance, x_coords, y_coords = _get_task_data(request.task_id)

        # 计算基线
        baseline_results = sampling_preview._calculate_baseline(
            existing_points, existing_values, request.grid_resolution
        )
        baseline_mean_variance = baseline_results['mean_variance']

        # 模拟每个方案
        logger.info(f"批量模拟 {len(request.sampling_plans)} 个采样方案")
        results = []

        for plan in request.sampling_plans:
            try:
                # 准备新点数据
                new_points = np.array([[p.x, p.y] for p in plan.points])
                new_values = np.array([p.value for p in plan.points])

                # 合并数据
                combined_points = np.vstack([existing_points, new_points])
                combined_values = np.append(existing_values, new_values)

                # 计算新方差
                new_results = sampling_preview._calculate_with_new_point(  # noqa: F841
                    existing_points, existing_values,
                    new_points[0], new_values[0],  # 使用第一个点作为参考
                    request.grid_resolution
                )

                # 重新计算所有新点
                from pykrige.ok import OrdinaryKriging
                ok = OrdinaryKriging(
                    combined_points[:, 0], combined_points[:, 1], combined_values,
                    variogram_model="spherical",
                    nlags=6,
                    enable_plotting=False
                )

                grid_x = baseline_results['grid_x']
                grid_y = baseline_results['grid_y']
                _, new_variance = ok.execute('grid', grid_x, grid_y)

                # 计算指标
                variance_reduction = baseline_results['variance'] - new_variance
                total_variance_reduction = np.sum(variance_reduction)

                baseline_rmse = np.sqrt(baseline_mean_variance)
                new_rmse = np.sqrt(np.mean(new_variance))
                rmse_improvement = ((baseline_rmse - new_rmse) / baseline_rmse * 100) if baseline_rmse > 0 else 0

                results.append(SimulationResult(
                    plan_id=plan.plan_id,
                    name=plan.name,
                    n_points=len(plan.points),
                    mean_variance=float(np.mean(new_variance)),
                    max_variance=float(np.max(new_variance)),
                    total_variance_reduction=float(total_variance_reduction),
                    rmse_improvement=float(rmse_improvement)
                ))

            except Exception as e:
                logger.error(f"模拟方案 {plan.plan_id} 失败: {str(e)}")
                # 添加失败的结果
                results.append(SimulationResult(
                    plan_id=plan.plan_id,
                    name=plan.name,
                    n_points=len(plan.points),
                    mean_variance=0.0,
                    max_variance=0.0,
                    total_variance_reduction=0.0,
                    rmse_improvement=0.0
                ))

        # 生成对比分析
        if results:
            comparison = {
                "best_plan": max(results, key=lambda x: x.total_variance_reduction).plan_id,
                "best_rmse_improvement": max(results, key=lambda x: x.rmse_improvement).plan_id,
                "mean_variance_reduction": float(np.mean([r.total_variance_reduction for r in results])),
                "mean_rmse_improvement": float(np.mean([r.rmse_improvement for r in results]))
            }
        else:
            comparison = {}

        return BatchSimulateResponse(
            task_id=request.task_id,
            n_plans=len(request.sampling_plans),
            results=results,
            comparison=comparison,
            simulated_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量模拟失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量模拟失败: {str(e)}")
