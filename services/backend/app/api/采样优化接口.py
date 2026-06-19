"""
采样优化接口 - 自适应采样流程控制
Adaptive Sampling Optimization API
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from adaptive_sampling.采样点推荐生成 import SamplingRecommender
from adaptive_sampling.高不确定性区域识别 import HighUncertaintyIdentifier
from adaptive_sampling.采样策略评估 import SamplingStrategyEvaluator
from adaptive_sampling.采样策略融合 import SamplingFusionEngine

from ..dependencies import verify_task_id
from ..config import settings
from ..tasks.任务管理器 import TaskManager

logger = logging.getLogger(__name__)

router = APIRouter()
task_manager = TaskManager()
sampling_recommender = SamplingRecommender()
uncertainty_identifier = HighUncertaintyIdentifier()
strategy_evaluator = SamplingStrategyEvaluator()
strategy_fusion = SamplingFusionEngine()

# 存储自适应采样会话
adaptive_sessions: Dict[str, Dict[str, Any]] = {}


# ==================== 数据模型（内联定义以减小依赖） ====================

class AdaptiveSamplingConfig:
    """自适应采样配置"""
    def __init__(
        self,
        task_id: str,
        strategy: str = "hybrid",
        n_recommendations: int = 20,
        threshold_percentile: float = 75,
        max_iterations: int = 10,
        convergence_threshold: float = 0.05,
        min_improvement: float = 0.01,
        patience: int = 3,
        industry: str = "unknown",
    ):
        self.task_id = task_id
        self.strategy = strategy
        self.n_recommendations = n_recommendations
        self.threshold_percentile = threshold_percentile
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.min_improvement = min_improvement
        self.patience = patience
        self.industry = industry


# ==================== 自适应采样接口 ====================

@router.post("/sampling-optimization/adaptive/start")
async def start_adaptive_sampling(
    task_id: str,
    strategy: str = "hybrid",
    n_recommendations: int = 20,
    threshold_percentile: float = 75,
    max_iterations: int = 10,
    convergence_threshold: float = 0.05,
    min_improvement: float = 0.01,
    patience: int = 3,
    industry: str = "unknown",
):
    """
    启动自适应采样会话

    自适应采样是一个迭代过程：
    1. 基于当前方差场生成采样建议
    2. 执行采样并更新模型
    3. 检查收敛条件
    4. 重复直到收敛或达到最大迭代次数

    参数:
    - task_id: 关联的插值任务ID
    - strategy: 采样策略 (variance_based/spatial_coverage/hybrid/impact_optimized)
    - n_recommendations: 每次迭代建议的采样点数量
    - threshold_percentile: 高不确定性阈值百分位
    - max_iterations: 最大迭代次数
    - convergence_threshold: 收敛阈值（方差减少低于此值视为收敛）
    - min_improvement: 最小改进量
    - patience: 早停耐心值（连续无改进迭代次数）
    - industry: 行业类型
    """
    try:
        verify_task_id(task_id)

        session_id = f"adaptive_{uuid.uuid4().hex[:12]}"

        session = {
            "session_id": session_id,
            "task_id": task_id,
            "config": {
                "strategy": strategy,
                "n_recommendations": n_recommendations,
                "threshold_percentile": threshold_percentile,
                "max_iterations": max_iterations,
                "convergence_threshold": convergence_threshold,
                "min_improvement": min_improvement,
                "patience": patience,
                "industry": industry,
            },
            "status": "initialized",
            "iterations": [],
            "statistics": {
                "total_variance_history": [],
                "improvement_history": [],
                "convergence_score": None,
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None,
        }

        adaptive_sessions[session_id] = session

        logger.info(f"自适应采样会话已创建: {session_id}, task_id={task_id}")

        return {
            "success": True,
            "message": "自适应采样会话已创建",
            "data": {
                "session_id": session_id,
                "task_id": task_id,
                "status": "initialized",
                "config": session["config"],
                "created_at": session["created_at"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动自适应采样失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动自适应采样失败: {str(e)}")


@router.post("/sampling-optimization/adaptive/iterate")
async def adaptive_sampling_iterate(
    session_id: str,
    existing_points: Optional[str] = None,
):
    """
    执行一次自适应采样迭代

    每轮迭代包含：
    1. 读取当前方差场数据
    2. 生成采样建议
    3. 评估策略性能
    4. 检查收敛条件
    5. 返回建议的采样点和状态

    参数:
    - session_id: 会话ID
    - existing_points: JSON格式的现有采样点（可选），格式:
      [{"x": 1.0, "y": 2.0}, ...]
    """
    try:
        if session_id not in adaptive_sessions:
            raise HTTPException(status_code=404, detail="自适应采样会话不存在")

        session = adaptive_sessions[session_id]

        if session["status"] in ("completed", "converged", "stopped"):
            raise HTTPException(status_code=400, detail=f"会话已结束，状态: {session['status']}")

        session["status"] = "running"
        session["updated_at"] = datetime.now().isoformat()
        iteration_num = len(session["iterations"]) + 1

        # 检查是否超过最大迭代次数
        if iteration_num > session["config"]["max_iterations"]:
            session["status"] = "completed"
            session["completed_at"] = datetime.now().isoformat()
            return {
                "success": True,
                "message": "已达到最大迭代次数，自适应采样完成",
                "data": {
                    "session_id": session_id,
                    "status": "completed",
                    "iteration": iteration_num - 1,
                    "recommendations": [],
                    "convergence": {
                        "converged": False,
                        "reason": "达到最大迭代次数",
                    },
                },
            }

        # 解析现有采样点
        existing_points_list = None
        if existing_points:
            import json
            points_data = json.loads(existing_points)
            existing_points_list = np.array([[p["x"], p["y"]] for p in points_data])

        # 读取方差数据
        variance_path = settings.RESULTS_DIR / f"{session['task_id']}_variance.tif"
        variance = None
        x_coords = None
        y_coords = None

        if variance_path.exists():
            from osgeo import gdal
            dataset = gdal.Open(str(variance_path))
            if dataset is not None:
                variance = dataset.GetRasterBand(1).ReadAsArray()
                transform = dataset.GetGeoTransform()
                cols = dataset.RasterXSize
                rows = dataset.RasterYSize
                x_coords = np.array([transform[0] + transform[1] * x for x in range(cols)])
                y_coords = np.array([transform[3] + transform[5] * y for y in range(rows)])
                dataset = None

        # 生成采样建议
        recommendations = []
        statistics = {}

        if variance is not None and x_coords is not None:
            try:
                # 使用采样推荐器生成建议
                base_result = sampling_recommender.generate_recommendations(
                    variance=variance,
                    x_coords=x_coords,
                    y_coords=y_coords,
                    existing_points=existing_points_list,
                    n_recommendations=session["config"]["n_recommendations"],
                    strategy=session["config"]["strategy"],
                    industry=session["config"]["industry"],
                )

                for idx, rec in enumerate(base_result.get("recommendations", [])):
                    variance_percentile_val = (
                        np.percentile(variance, rec["variance"] * 100 / np.max(variance))
                        if np.max(variance) > 0 else 0
                    )
                    uncertainty_level = max(1, min(5, int(np.ceil(variance_percentile_val * 5 / 100))))

                    recommendations.append({
                        "id": idx + 1,
                        "x": float(rec["x"]),
                        "y": float(rec["y"]),
                        "variance": float(rec.get("variance", 0.0)),
                        "priority": rec.get("priority", "medium"),
                        "uncertainty_level": uncertainty_level,
                        "sampling_reason": rec.get("reason", "高不确定性区域"),
                    })

                statistics = {
                    "total_variance": float(np.sum(variance)),
                    "mean_variance": float(np.mean(variance)),
                    "max_variance": float(np.max(variance)),
                    "n_recommendations": len(recommendations),
                }
            except Exception as e:
                logger.warning(f"生成采样建议时出错: {str(e)}，返回模拟数据")
                recommendations = _generate_fallback_recommendations(
                    session["config"]["n_recommendations"]
                )
                statistics = {
                    "total_variance": 0.0,
                    "mean_variance": 0.0,
                    "max_variance": 0.0,
                    "n_recommendations": len(recommendations),
                    "warning": f"使用模拟数据: {str(e)}",
                }
        else:
            logger.warning("方差栅格文件不存在，使用模拟数据生成建议")
            recommendations = _generate_fallback_recommendations(
                session["config"]["n_recommendations"]
            )
            statistics = {
                "total_variance": 0.0,
                "mean_variance": 0.0,
                "max_variance": 0.0,
                "n_recommendations": len(recommendations),
                "warning": "方差栅格文件不存在，使用模拟数据",
            }

        # 收敛性检查
        total_variance = statistics.get("total_variance", 0.0)
        session["statistics"]["total_variance_history"].append(total_variance)

        converged = False
        convergence_reason = ""

        if iteration_num > 1:
            prev_variance = session["statistics"]["total_variance_history"][-2]
            improvement = prev_variance - total_variance
            improvement_rate = improvement / max(prev_variance, 1e-10)
            session["statistics"]["improvement_history"].append(improvement_rate)

            # 检查收敛
            if improvement_rate < session["config"]["convergence_threshold"]:
                # 检查耐心值
                patience = session["config"]["patience"]
                recent_improvements = session["statistics"]["improvement_history"][-patience:]
                if all(imp < session["config"]["min_improvement"] for imp in recent_improvements):
                    converged = True
                    convergence_reason = f"连续{patience}次迭代改进量低于阈值"
        else:
            session["statistics"]["improvement_history"].append(1.0)

        # 记录迭代信息
        iteration_record = {
            "iteration": iteration_num,
            "n_recommendations": len(recommendations),
            "total_variance": total_variance,
            "converged": converged,
            "timestamp": datetime.now().isoformat(),
        }
        session["iterations"].append(iteration_record)

        # 更新收敛分数
        if len(session["statistics"]["total_variance_history"]) >= 2:
            variance_history = session["statistics"]["total_variance_history"]
            if variance_history[0] > 0:
                convergence_score = 1.0 - (variance_history[-1] / variance_history[0])
                session["statistics"]["convergence_score"] = max(0.0, min(1.0, convergence_score))

        # 更新会话状态
        if converged:
            session["status"] = "converged"
            session["completed_at"] = datetime.now().isoformat()
        else:
            session["status"] = "running"

        session["updated_at"] = datetime.now().isoformat()

        return {
            "success": True,
            "message": f"迭代 {iteration_num} 完成" + (" - 已收敛" if converged else ""),
            "data": {
                "session_id": session_id,
                "status": session["status"],
                "iteration": iteration_num,
                "recommendations": recommendations,
                "statistics": statistics,
                "convergence": {
                    "converged": converged,
                    "reason": convergence_reason if converged else "未收敛",
                    "score": session["statistics"]["convergence_score"],
                    "history": session["statistics"]["improvement_history"][-5:],
                },
                "remaining_iterations": max(0, session["config"]["max_iterations"] - iteration_num),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"自适应采样迭代失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"自适应采样迭代失败: {str(e)}")


@router.post("/sampling-optimization/adaptive/stop")
async def stop_adaptive_sampling(session_id: str):
    """
    停止自适应采样会话

    参数:
    - session_id: 会话ID
    """
    try:
        if session_id not in adaptive_sessions:
            raise HTTPException(status_code=404, detail="自适应采样会话不存在")

        session = adaptive_sessions[session_id]

        if session["status"] in ("completed", "converged", "stopped"):
            raise HTTPException(
                status_code=400,
                detail=f"会话已经处于终止状态: {session['status']}",
            )

        # 停止会话
        session["status"] = "stopped"
        session["completed_at"] = datetime.now().isoformat()
        session["updated_at"] = datetime.now().isoformat()
        session["stop_reason"] = "用户手动停止"

        total_iterations = len(session["iterations"])
        total_recommendations = sum(
            it.get("n_recommendations", 0) for it in session["iterations"]
        )

        logger.info(f"自适应采样会话已停止: {session_id}, 共{total_iterations}次迭代")

        return {
            "success": True,
            "message": "自适应采样会话已停止",
            "data": {
                "session_id": session_id,
                "status": "stopped",
                "total_iterations": total_iterations,
                "total_recommendations": total_recommendations,
                "final_variance": session["statistics"]["total_variance_history"][-1]
                if session["statistics"]["total_variance_history"]
                else None,
                "convergence_score": session["statistics"]["convergence_score"],
                "completed_at": session["completed_at"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止自适应采样失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"停止自适应采样失败: {str(e)}")


@router.get("/sampling-optimization/adaptive/status")
async def get_adaptive_sampling_status(
    session_id: Optional[str] = Query(default=None),
):
    """
    获取自适应采样会话状态

    参数:
    - session_id: 会话ID（不提供则列出所有会话）
    """
    try:
        if session_id:
            if session_id not in adaptive_sessions:
                raise HTTPException(status_code=404, detail="自适应采样会话不存在")

            session = adaptive_sessions[session_id]
            return {
                "success": True,
                "message": "查询成功",
                "data": {
                    "session_id": session["session_id"],
                    "task_id": session["task_id"],
                    "status": session["status"],
                    "config": session["config"],
                    "iterations_count": len(session["iterations"]),
                    "iterations": session["iterations"],
                    "statistics": session["statistics"],
                    "created_at": session["created_at"],
                    "updated_at": session["updated_at"],
                    "completed_at": session["completed_at"],
                    "error": session.get("error"),
                },
            }
        else:
            # 列出所有会话
            sessions_list = []
            for sid, sess in adaptive_sessions.items():
                sessions_list.append({
                    "session_id": sid,
                    "task_id": sess["task_id"],
                    "status": sess["status"],
                    "iterations_count": len(sess["iterations"]),
                    "created_at": sess["created_at"],
                    "updated_at": sess["updated_at"],
                })

            return {
                "success": True,
                "message": f"共 {len(sessions_list)} 个会话",
                "data": {
                    "total": len(sessions_list),
                    "sessions": sessions_list,
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询自适应采样状态失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询状态失败: {str(e)}")


def _generate_fallback_recommendations(n_recommendations: int) -> List[Dict[str, Any]]:
    """当方差数据不可用时，生成模拟的采样建议用于功能测试"""
    recommendations = []
    for i in range(min(n_recommendations, 10)):
        recommendations.append({
            "id": i + 1,
            "x": round(100.0 + i * 2.5, 2),
            "y": round(30.0 + i * 1.5, 2),
            "variance": round(0.8 - i * 0.05, 4),
            "priority": "high" if i < 3 else "medium" if i < 7 else "low",
            "uncertainty_level": max(1, 5 - i // 2),
            "sampling_reason": "模拟推荐点，用于功能验证",
        })
    return recommendations
