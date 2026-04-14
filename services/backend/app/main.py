"""
FastAPI主应用
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
import uuid

# 添加项目根目录到Python路径
# 当前文件位于 services/backend/app/main.py，需要回退4层到仓库根目录
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from .config import settings
from .security_middleware import security_guard_middleware
from .startup_manager import StartupManager
from .services.websocket_service import websocket_service
from .services.智能工作流服务 import smart_workflow_service
from .api_versioning import (
    router as api_versioning_router,
    api_versioning_middleware,
    SUPPORTED_API_VERSIONS,
    CURRENT_API_VERSION,
    DEPRECATED_API_VERSIONS,
)
from .api_response import unified_api_response_middleware
from .api import 数据上传接口, 插值任务接口, 结果查询接口, 任务状态接口, 报告生成接口, 模型推荐接口, 采样建议接口, 采样点影响评估接口, 行业配置接口, 批量插值接口, 参数批量应用接口, 结果对比分析接口, 批量报告生成接口, 进度详情接口, 资源监控接口, 任务队列接口, 分布式计算接口, 性能报告接口, 不确定性分级接口, 风险指数接口, 决策阈值接口, 风险报告接口, 异常检测接口, 误差预测接口, 模型评估接口, 配置接口, 路径规划接口, 模型融合接口, 项目管理接口, 通用数据处理接口, 数据质量接口, 数据安全接口, GPU加速接口, 数据反馈接口, 主动学习接口, 用户验证与自评估接口, 移动端GPS接口, 历史对比与趋势分析接口, 智能工作流接口, 时空克里金接口
from .api.app_download_api import router as download_router
from .api.admin_api import router as admin_router
from .api.auth_api import router as auth_router
from .api.product_keys_api import router as product_keys_router
from .api.company_management_api import router as company_management_router
from .api.devices_api import router as devices_router
from .services.mobile_gps_service import mobile_gps_service

# 导入新增的系统路由
from realtime_interpolation.api import fastapi_routes as realtime_routes
from multi_objective_optimization.api import fastapi_routes as multi_objective_routes
from .kriging_3d.api.路由 import router as kriging_3d_router
from .dl_services.api import router as deep_learning_router
import logging

def _setup_logging() -> None:
    """按配置初始化日志输出（控制台 + 可选文件）。"""
    level_name = str(getattr(settings, "LOG_LEVEL", "INFO") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handlers = [logging.StreamHandler()]
    log_file = getattr(settings, "LOG_FILE", None)
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )


_setup_logging()

startup_manager = StartupManager()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """应用生命周期：启动阶段执行预加载与降级判定。"""
    app_instance.state.startup_manager = startup_manager
    try:
        snapshot = await startup_manager.run()
        logging.info("启动流程完成: %s", snapshot)
    except Exception as exc:  # pylint: disable=broad-except
        logging.exception("启动流程异常，进入降级模式: %s", exc)
        startup_manager.record_performance_event(
            "backend",
            {"event": "startup_exception", "error": str(exc)},
        )
    yield
    await startup_manager.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="基于克里金插值的空间不确定性分析平台",
    lifespan=lifespan,
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    info = openapi_schema.setdefault("info", {})
    info["x-api-versions"] = list(SUPPORTED_API_VERSIONS)
    info["x-current-version"] = CURRENT_API_VERSION
    info["x-deprecated-versions"] = DEPRECATED_API_VERSIONS
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# CORS中间件 —— 开发环境放行所有来源，避免 Capacitor/局域网调试时 origin 不匹配
if settings.is_development:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 挂载静态文件
app.mount("/results", StaticFiles(directory=str(settings.RESULTS_DIR)), name="results")
app.mount("/android_downloads", StaticFiles(directory=str(settings.ANDROID_APK_DIR)), name="android_downloads")


@app.middleware("http")
async def api_version_middleware(request: Request, call_next):
    """统一处理 API 版本解析、兼容重写与废弃告警。"""
    return await api_versioning_middleware(request, call_next)


@app.middleware("http")
async def api_response_format_middleware(request: Request, call_next):
    """统一处理 API v2 响应包装与请求元数据。"""
    return await unified_api_response_middleware(request, call_next)


# 注册路由
app.include_router(数据上传接口.router, prefix="/api", tags=["数据上传"])
app.include_router(插值任务接口.router, prefix="/api", tags=["插值任务"])
app.include_router(批量插值接口.router, tags=["批量插值"])
app.include_router(参数批量应用接口.router, tags=["参数批量应用"])
app.include_router(结果对比分析接口.router, tags=["结果对比分析"])
app.include_router(批量报告生成接口.router, tags=["批量报告生成"])
app.include_router(结果查询接口.router, prefix="/api", tags=["结果查询"])
app.include_router(任务状态接口.router, prefix="/api", tags=["任务状态"])
app.include_router(报告生成接口.router, prefix="/api", tags=["报告生成"])
app.include_router(模型推荐接口.router, prefix="/api", tags=["模型推荐"])
app.include_router(采样建议接口.router, prefix="/api", tags=["采样建议"])
app.include_router(采样点影响评估接口.router, prefix="/api/sampling-impact", tags=["采样点影响评估"])
app.include_router(行业配置接口.router, prefix="/api", tags=["行业配置"])
app.include_router(进度详情接口.router, prefix="/api", tags=["进度详情"])
app.include_router(资源监控接口.router, prefix="/api", tags=["资源监控"])
app.include_router(任务队列接口.router, prefix="/api", tags=["任务队列"])
app.include_router(分布式计算接口.router, prefix="/api", tags=["分布式计算"])
app.include_router(性能报告接口.router, prefix="/api", tags=["性能报告"])
app.include_router(历史对比与趋势分析接口.router, prefix="/api", tags=["历史对比与趋势分析"])
app.include_router(智能工作流接口.router, prefix="/api", tags=["智能工作流"])
app.include_router(不确定性分级接口.router, prefix="/api", tags=["不确定性分级"])
app.include_router(风险指数接口.router, prefix="/api", tags=["风险指数"])
app.include_router(决策阈值接口.router, prefix="/api", tags=["决策阈值"])
app.include_router(风险报告接口.router, prefix="/api", tags=["风险报告"])
app.include_router(异常检测接口.router, prefix="/api", tags=["异常检测"])
app.include_router(误差预测接口.router, prefix="/api", tags=["误差预测"])
app.include_router(模型评估接口.router, prefix="/api", tags=["模型评估"])
app.include_router(配置接口.router, tags=["配置管理"])
app.include_router(路径规划接口.router, tags=["路径规划"])
app.include_router(模型融合接口.router, prefix="/api", tags=["模型融合"])
app.include_router(项目管理接口.router, tags=["项目管理"])
app.include_router(通用数据处理接口.router, prefix="/api", tags=["通用数据处理"])
app.include_router(数据质量接口.router, prefix="/api", tags=["数据质量"])
app.include_router(数据安全接口.router, prefix="/api", tags=["数据安全"])
app.include_router(数据反馈接口.router, prefix="/api", tags=["数据反馈"])
app.include_router(主动学习接口.router, prefix="/api", tags=["主动学习与半监督"])
app.include_router(用户验证与自评估接口.router, prefix="/api", tags=["用户验证与模型自评估"])
app.include_router(GPU加速接口.router, prefix="/api", tags=["GPU加速"])
app.include_router(移动端GPS接口.router, tags=["移动端GPS"])
app.include_router(download_router, prefix="/api", tags=["下载"])
app.include_router(auth_router, prefix="/api", tags=["认证"])
app.include_router(product_keys_router, prefix="/api", tags=["密钥"])
app.include_router(devices_router, prefix="/api", tags=["设备管理"])
app.include_router(company_management_router, prefix="/api", tags=["企业管理"])
app.include_router(admin_router, prefix="/api", tags=["管理员后台"])
app.include_router(api_versioning_router)

# 注册新增的系统路由
app.include_router(realtime_routes.router, prefix="/api", tags=["实时插值"])
app.include_router(multi_objective_routes.router, prefix="/api", tags=["多目标优化"])

# 注册3D克里金路由
app.include_router(kriging_3d_router, prefix="/api", tags=["3D克里金"])

# 注册深度学习路由
app.include_router(deep_learning_router, prefix="/api", tags=["深度学习"])
app.include_router(时空克里金接口.router, prefix="/api", tags=["时空克里金"])


@app.middleware("http")
async def startup_error_middleware(request: Request, call_next):
    """统一启动/运行期异常处理，返回可追踪错误ID。"""
    try:
        response = await call_next(request)
        return response
    except Exception as exc:  # pylint: disable=broad-except
        error_id = uuid.uuid4().hex[:12]
        logging.exception("请求处理异常[%s]: %s", error_id, exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "服务暂时不可用，请稍后重试",
                "error_id": error_id,
                "detail": str(exc),
            },
        )


@app.middleware("http")
async def auth_security_middleware(request: Request, call_next):
    """统一安全防护中间件：IP黑名单、CSRF、XSS与安全响应头。"""
    return await security_guard_middleware(request, call_next)

@app.get("/")
async def root():
    return {
        "message": "智能不确定性驱动空间决策平台",
        "version": settings.VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    snapshot = startup_manager.get_health_snapshot()
    return {
        "status": "healthy",
        "startup_ready": snapshot["ready"],
        "startup_degradation_level": snapshot["degradation_level"],
    }


@app.get("/api/startup/health")
async def startup_health_check():
    """启动健康检查接口。"""
    snapshot = startup_manager.get_health_snapshot()
    status_code = 200 if snapshot.get("ready", False) else 503
    return JSONResponse(status_code=status_code, content=snapshot)


@app.get("/api/startup/performance")
async def startup_performance_report(limit: int = Query(default=50, ge=1, le=200)):
    """启动性能监控查询接口。"""
    return startup_manager.get_performance_report(limit=limit)


@app.post("/api/startup/performance")
async def startup_performance_ingest(payload: dict):
    """启动性能实时上报接口。"""
    startup_manager.record_performance_event("frontend", payload)
    return {"ok": True}

# WebSocket 端点
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    user_id: Optional[str] = Query(default=None),
    reconnect: bool = Query(default=False),
):
    await websocket_service.connect(
        websocket,
        client_id,
        user_id=user_id,
        restore_subscriptions=bool(reconnect),
    )
    try:
        while True:
            data = await websocket.receive_json()
            websocket_service.touch(client_id, received_message=True)
            await handle_websocket_message(client_id, data)
    except WebSocketDisconnect:
        websocket_service.disconnect(client_id)


def _get_field(message: dict, key: str, default=None):
    if key in message:
        return message.get(key, default)
    return (message.get("data") or {}).get(key, default)


def _has_workflow_access(workflow_id: str, user_id: str) -> bool:
    wid = str(workflow_id or "").strip()
    uid = str(user_id or "").strip()
    if not wid:
        return False
    if not uid:
        return True
    try:
        workflow = smart_workflow_service.get_workflow(wid)
        if not workflow:
            return True
    except Exception:
        return True
    permissions = ("read_workflow", "edit_workflow", "comment", "update_cursor", "manage_collaborators")
    for permission in permissions:
        try:
            if smart_workflow_service.has_permission(wid, uid, permission):
                return True
        except Exception:
            continue
    return False


async def _dispatch_queued_message(queue_item: dict) -> None:
    payload = (queue_item or {}).get("payload") or {}
    message_type = str(payload.get("message_type") or "")
    if message_type == "notification":
        user_id = str(payload.get("user_id") or "")
        notification = dict(payload.get("notification") or {})
        if not user_id:
            return
        n_type = str(notification.get("type") or "notification")
        outbound_type = "mention" if n_type == "mention" else "notification"
        await websocket_service.send_to_user(
            websocket_service.build_message(outbound_type, data=notification, user_id=user_id),
            user_id,
        )


async def handle_websocket_message(client_id: str, message: dict):
    err = websocket_service.validate_message(message)
    if err:
        await websocket_service.send_personal_message(
            websocket_service.build_message("error", data={"message": err}),
            client_id,
        )
        return

    message_type = message.get('type')
    message_data = message.get("data") or {}
    workflow_for_limit = (
        _get_field(message, "workflow_id")
        or _get_field(message, "run_id")
        or ""
    )
    connected_user_id = websocket_service.get_client_user_id(client_id)
    effective_user_id = connected_user_id or str(_get_field(message, "user_id") or "")
    rate_error = websocket_service.enforce_rate_limit(
        client_id=client_id,
        workflow_id=str(workflow_for_limit or ""),
        user_id=str(effective_user_id or ""),
    )
    if rate_error:
        await websocket_service.send_personal_message(
            websocket_service.build_message("error", data={"message": rate_error}),
            client_id,
        )
        return
    message_id = message.get("message_id") or message_data.get("message_id")

    if message_type == 'subscribe_task':
        task_id = _get_field(message, "task_id")
        await websocket_service.subscribe_to_task(client_id, task_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message(
                'subscription_confirmed',
                message_id=message_id,
                data={"task_id": task_id},
                task_id=task_id,
            ),
            client_id,
        )

    elif message_type == 'unsubscribe_task':
        task_id = _get_field(message, "task_id")
        await websocket_service.unsubscribe_from_task(client_id, task_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message(
                'unsubscription_confirmed',
                message_id=message_id,
                data={"task_id": task_id},
                task_id=task_id,
            ),
            client_id,
        )

    elif message_type == 'subscribe_workflow':
        workflow_id = _get_field(message, "workflow_id")
        if not workflow_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "workflow_id is required"}),
                client_id,
            )
            return
        if connected_user_id and not _has_workflow_access(str(workflow_id), connected_user_id):
            await websocket_service.send_personal_message(
                websocket_service.build_message(
                    "error",
                    message_id=message_id,
                    data={"message": "workflow access denied"},
                ),
                client_id,
            )
            return
        await websocket_service.subscribe_to_workflow(client_id, workflow_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message(
                'subscription_confirmed',
                message_id=message_id,
                data={"workflow_id": workflow_id},
                workflow_id=workflow_id,
            ),
            client_id,
        )

    elif message_type == 'unsubscribe_workflow':
        workflow_id = _get_field(message, "workflow_id")
        if not workflow_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "workflow_id is required"}),
                client_id,
            )
            return
        await websocket_service.unsubscribe_from_workflow(client_id, workflow_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message(
                'unsubscription_confirmed',
                message_id=message_id,
                data={"workflow_id": workflow_id},
                workflow_id=workflow_id,
            ),
            client_id,
        )

    elif message_type == 'subscribe_workflow_run':
        run_id = _get_field(message, "run_id")
        if not run_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "run_id is required"}),
                client_id,
            )
            return
        if connected_user_id:
            try:
                run_detail = smart_workflow_service.get_run(str(run_id))
                run_workflow_id = str((run_detail or {}).get("workflow_id") or "")
                if run_workflow_id and not _has_workflow_access(run_workflow_id, connected_user_id):
                    await websocket_service.send_personal_message(
                        websocket_service.build_message(
                            "error",
                            message_id=message_id,
                            data={"message": "workflow run access denied"},
                        ),
                        client_id,
                    )
                    return
            except Exception:
                pass
        await websocket_service.subscribe_to_workflow_run(client_id, run_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message('subscription_confirmed', message_id=message_id, data={"run_id": run_id}, run_id=run_id),
            client_id,
        )

    elif message_type == 'unsubscribe_workflow_run':
        run_id = _get_field(message, "run_id")
        if not run_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "run_id is required"}),
                client_id,
            )
            return
        await websocket_service.unsubscribe_from_workflow_run(client_id, run_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message('unsubscription_confirmed', message_id=message_id, data={"run_id": run_id}, run_id=run_id),
            client_id,
        )

    elif message_type in {"subscribe_user_notifications", "subscribe_user_mentions", "subscribe_user_activity"}:
        user_id = str(_get_field(message, "user_id") or "").strip()
        if not user_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "user_id is required"}),
                client_id,
            )
            return
        if connected_user_id and connected_user_id != user_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "forbidden user subscription"}),
                client_id,
            )
            return
        channel = (
            "mention"
            if message_type.endswith("mentions")
            else "activity"
            if message_type.endswith("activity")
            else "notification"
        )
        websocket_service.subscribe_user_channel(client_id=client_id, user_id=user_id, channel=channel)
        await websocket_service.send_personal_message(
            websocket_service.build_message(
                "subscription_confirmed",
                message_id=message_id,
                data={"user_id": user_id, "channel": channel},
                user_id=user_id,
            ),
            client_id,
        )

    elif message_type in {"unsubscribe_user_notifications", "unsubscribe_user_mentions", "unsubscribe_user_activity"}:
        user_id = str(_get_field(message, "user_id") or "").strip()
        if not user_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "user_id is required"}),
                client_id,
            )
            return
        channel = (
            "mention"
            if message_type.endswith("mentions")
            else "activity"
            if message_type.endswith("activity")
            else "notification"
        )
        websocket_service.unsubscribe_user_channel(client_id=client_id, user_id=user_id, channel=channel)
        await websocket_service.send_personal_message(
            websocket_service.build_message(
                "unsubscription_confirmed",
                message_id=message_id,
                data={"user_id": user_id, "channel": channel},
                user_id=user_id,
            ),
            client_id,
        )

    elif message_type == 'subscribe_gps_project':
        project_id = _get_field(message, "project_id", 'default_mobile_project')
        await websocket_service.subscribe_to_project(client_id, project_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message('subscription_confirmed', message_id=message_id, data={"project_id": project_id}, project_id=project_id),
            client_id,
        )

    elif message_type == 'unsubscribe_gps_project':
        project_id = _get_field(message, "project_id", 'default_mobile_project')
        await websocket_service.unsubscribe_from_project(client_id, project_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message('unsubscription_confirmed', message_id=message_id, data={"project_id": project_id}, project_id=project_id),
            client_id,
        )

    elif message_type == 'gps_sample_upsert':
        sample = message_data.get('sample') or {}
        project_id = (
            message_data.get('project_id')
            or sample.get('project_id')
            or sample.get('projectId')
            or 'default_mobile_project'
        )
        result = mobile_gps_service.upsert_samples(
            client_id=client_id,
            samples=[sample],
            strategy=message_data.get('strategy', 'latest-wins')
        )
        await websocket_service.send_personal_message(
            websocket_service.build_message('ack', message_id=message_id, data=result),
            client_id,
        )

        if result.get('applied_samples'):
            for applied in result['applied_samples']:
                await websocket_service.notify_gps_update(
                    project_id=project_id,
                    sample=applied,
                    exclude_client_id=client_id
                )

    elif message_type in {'collaboration_cursor_update', 'cursor_update'}:
        workflow_id = _get_field(message, "workflow_id")
        cursor_position = _get_field(message, "cursor_position") or _get_field(message, "cursor") or {}
        color = str(_get_field(message, "color", "#409eff"))
        user_id = _get_field(message, "user_id")

        if not workflow_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "workflow_id is required"}),
                client_id,
            )
            return

        if not user_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "user_id is required"}),
                client_id,
            )
            return
        permission_error = websocket_service.validate_message_permission(
            client_id=client_id,
            sender_user_id=str(user_id),
        )
        if permission_error:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": permission_error}),
                client_id,
            )
            return
        if connected_user_id and not _has_workflow_access(str(workflow_id), connected_user_id):
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "workflow access denied"}),
                client_id,
            )
            return

        try:
            cursor_result = websocket_service.process_cursor_update(
                workflow_id=str(workflow_id),
                user_id=str(user_id),
                cursor_position=cursor_position,
                color=color,
                client_timestamp=_get_field(message, "timestamp"),
            )
            persisted_cursor = cursor_result["cursor"]
            try:
                result = smart_workflow_service.update_collaboration_cursor(
                    workflow_id=str(workflow_id),
                    user_id=str(user_id),
                    position={
                        'node_id': cursor_position.get('node_id') or '',
                        'x': cursor_position.get('x', 0.0),
                        'y': cursor_position.get('y', 0.0),
                        'selection': cursor_position.get('selection') or [],
                    },
                )
                persisted_cursor = result.get('cursor') or persisted_cursor
            except Exception:
                pass

            if cursor_result["changed"] and not cursor_result["throttled"]:
                await websocket_service.broadcast_to_group(
                    "workflow",
                    str(workflow_id),
                    websocket_service.build_message(
                        "cursor_update",
                        data=cursor_result["cursor"],
                        workflow_id=str(workflow_id),
                        user_id=str(user_id),
                    ),
                    exclude_client_id=client_id,
                )
            await websocket_service.send_personal_message(
                websocket_service.build_message(
                    'ack',
                    message_id=message_id,
                    data={
                        "workflow_id": workflow_id,
                        "cursor": persisted_cursor,
                        "throttled": cursor_result["throttled"],
                        "changed": cursor_result["changed"],
                    },
                    workflow_id=workflow_id,
                ),
                client_id,
            )
        except Exception as exc:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": str(exc)}),
                client_id,
            )

    elif message_type == "collaboration_operation":
        workflow_id = _get_field(message, "workflow_id")
        user_id = _get_field(message, "user_id")
        operation_type = _get_field(message, "operation_type")
        operation_data = _get_field(message, "operation_data", {}) or {}
        if not workflow_id or not user_id or not operation_type:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "workflow_id/user_id/operation_type is required"}),
                client_id,
            )
            return
        permission_error = websocket_service.validate_message_permission(
            client_id=client_id,
            sender_user_id=str(user_id),
        )
        if permission_error:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": permission_error}),
                client_id,
            )
            return
        if connected_user_id and not _has_workflow_access(str(workflow_id), connected_user_id):
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "workflow access denied"}),
                client_id,
            )
            return
        try:
            op = websocket_service.record_collaboration_operation(
                workflow_id=str(workflow_id),
                user_id=str(user_id),
                operation_type=str(operation_type),
                operation_data=operation_data,
                sequence=_get_field(message, "sequence"),
            )
            await websocket_service.broadcast_to_group(
                "workflow",
                str(workflow_id),
                websocket_service.build_message("collaboration_operation", data=op, workflow_id=str(workflow_id)),
                exclude_client_id=client_id,
            )
            await websocket_service.send_personal_message(
                websocket_service.build_message("ack", message_id=message_id, data=op),
                client_id,
            )
        except Exception as exc:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": str(exc)}),
                client_id,
            )

    elif message_type == "comment_created":
        workflow_id = _get_field(message, "workflow_id")
        comment_id = _get_field(message, "comment_id")
        user_id = _get_field(message, "user_id")
        content = _get_field(message, "content")
        parent_id = _get_field(message, "parent_id")
        if not workflow_id or not comment_id or not user_id or not content:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "workflow_id/comment_id/user_id/content is required"}),
                client_id,
            )
            return
        permission_error = websocket_service.validate_message_permission(
            client_id=client_id,
            sender_user_id=str(user_id),
        )
        if permission_error:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": permission_error}),
                client_id,
            )
            return
        if connected_user_id and not _has_workflow_access(str(workflow_id), connected_user_id):
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "workflow access denied"}),
                client_id,
            )
            return
        content_error = websocket_service.validate_message_content(str(content))
        if content_error:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": content_error}),
                client_id,
            )
            return
        try:
            comment = websocket_service.record_comment(
                workflow_id=str(workflow_id),
                comment_id=str(comment_id),
                user_id=str(user_id),
                content=str(content),
                parent_id=str(parent_id or ""),
                timestamp=_get_field(message, "timestamp"),
            )
            await websocket_service.broadcast_to_group(
                "workflow",
                str(workflow_id),
                websocket_service.build_message("comment_created", data=comment, workflow_id=str(workflow_id)),
                exclude_client_id=None,
            )
            for mention_user in comment.get("mentions") or []:
                notification = websocket_service.build_message(
                    "notification",
                    data={
                        "notification_id": f"ntf_{mention_user}_{int(datetime.now().timestamp() * 1000)}",
                        "type": "mention",
                        "title": "评论提及",
                        "content": f"{user_id} 在评论中提及了你",
                        "workflow_id": str(workflow_id),
                        "comment_id": str(comment_id),
                        "user_id": str(mention_user),
                    },
                )
                await websocket_service.send_to_user(notification, str(mention_user))
            await websocket_service.send_personal_message(
                websocket_service.build_message("ack", message_id=message_id, data=comment),
                client_id,
            )
        except Exception as exc:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": str(exc)}),
                client_id,
            )

    elif message_type == "notification":
        notification_payload = {
            "user_id": _get_field(message, "user_id"),
            "notification_id": _get_field(message, "notification_id"),
            "type": _get_field(message, "type"),
            "title": _get_field(message, "title"),
            "content": _get_field(message, "content"),
            "timestamp": _get_field(message, "timestamp", datetime.now().isoformat()),
        }
        missing = [k for k in ("user_id", "notification_id", "type", "title", "content") if not notification_payload.get(k)]
        if missing:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": f"missing fields: {','.join(missing)}"}),
                client_id,
            )
            return
        permission_error = websocket_service.validate_message_permission(
            client_id=client_id,
            sender_user_id=connected_user_id,
            receiver_user_id=str(notification_payload.get("user_id") or ""),
        )
        if permission_error:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": permission_error}),
                client_id,
            )
            return
        title_error = websocket_service.validate_message_content(
            str(notification_payload.get("title") or ""),
            max_length=120,
        )
        content_error = websocket_service.validate_message_content(str(notification_payload.get("content") or ""))
        if title_error or content_error:
            await websocket_service.send_personal_message(
                websocket_service.build_message(
                    "error",
                    message_id=message_id,
                    data={"message": title_error or content_error},
                ),
                client_id,
            )
            return
        result = websocket_service.queue_notification(
            notification=notification_payload,
            priority=str(_get_field(message, "priority", "high")),
        )
        if not result.get("deduplicated"):
            await websocket_service.process_message_batch(_dispatch_queued_message, batch_size=50)
        await websocket_service.send_personal_message(
            websocket_service.build_message("ack", message_id=message_id, data=result),
            client_id,
        )

    elif message_type == "share_access":
        share_token = _get_field(message, "share_token")
        workflow_id = _get_field(message, "workflow_id")
        visitor_id = _get_field(message, "visitor_id", "anonymous")
        access_time = _get_field(message, "access_time", datetime.now().isoformat())
        access_type = _get_field(message, "access_type", "view")
        if not share_token or not workflow_id:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "share_token/workflow_id is required"}),
                client_id,
            )
            return
        stats = websocket_service.record_share_access(
            share_token=str(share_token),
            workflow_id=str(workflow_id),
            visitor_id=str(visitor_id),
            access_time=str(access_time),
            access_type=str(access_type),
        )
        await websocket_service.broadcast_to_group(
            "workflow",
            str(workflow_id),
            websocket_service.build_message("share_access", data=stats, workflow_id=str(workflow_id)),
            exclude_client_id=None,
        )
        await websocket_service.send_personal_message(
            websocket_service.build_message("ack", message_id=message_id, data=stats),
            client_id,
        )

    elif message_type == "conflict_resolution":
        workflow_id = _get_field(message, "workflow_id")
        conflict_id = _get_field(message, "conflict_id")
        user_id = _get_field(message, "user_id")
        resolution_type = _get_field(message, "resolution_type")
        resolution_data = _get_field(message, "resolution_data", {}) or {}
        allowed = {"accept", "override", "merge", "keep_both"}
        if not workflow_id or not conflict_id or not user_id or resolution_type not in allowed:
            await websocket_service.send_personal_message(
                websocket_service.build_message("error", message_id=message_id, data={"message": "invalid conflict_resolution payload"}),
                client_id,
            )
            return
        payload = {
            "workflow_id": str(workflow_id),
            "conflict_id": str(conflict_id),
            "user_id": str(user_id),
            "resolution_type": str(resolution_type),
            "resolution_data": resolution_data,
            "timestamp": _get_field(message, "timestamp", datetime.now().isoformat()),
        }
        await websocket_service.broadcast_to_group(
            "workflow",
            str(workflow_id),
            websocket_service.build_message("conflict_resolution", data=payload, workflow_id=str(workflow_id)),
            exclude_client_id=None,
        )
        await websocket_service.send_personal_message(
            websocket_service.build_message("ack", message_id=message_id, data=payload),
            client_id,
        )

    elif message_type in {'gps_ping', 'ping', 'heartbeat_pong'}:
        websocket_service.receive_heartbeat(client_id)
        await websocket_service.send_personal_message(
            websocket_service.build_message(
                'gps_pong' if message_type == 'gps_ping' else 'pong',
                message_id=message_id,
                data={"heartbeat_ok": True},
            ),
            client_id,
        )

    elif message_type == 'ack':
        ack_id = _get_field(message, "ack_id") or message_data.get('message_id') or message_data.get('id') or message_id
        if ack_id:
            await websocket_service.confirm_ack(client_id, ack_id)

    elif message_type == "connection_stats":
        await websocket_service.send_personal_message(
            websocket_service.build_message(
                "connection_stats",
                data={
                    **websocket_service.get_connection_stats(),
                    "subscriptions": websocket_service.list_client_subscriptions(client_id),
                },
                message_id=message_id,
            ),
            client_id,
        )

    else:
        await websocket_service.send_personal_message(
            websocket_service.build_message("error", message_id=message_id, data={"message": f"unsupported message type: {message_type}"}),
            client_id,
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
