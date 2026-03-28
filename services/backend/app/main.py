"""
FastAPI主应用
"""
import sys
import os
import warnings
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
import uuid

# 添加项目根目录到Python路径
# 当前文件位于 services/backend/app/main.py，需要回退4层到仓库根目录
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

# 抑制 starlette 对 multipart 导入兼容层的待弃用提示
warnings.filterwarnings(
    "ignore",
    message=".*import python_multipart.*",
    category=PendingDeprecationWarning
)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from .config import settings
from .security_middleware import security_guard_middleware
from .startup_manager import StartupManager
from .services.websocket_service import websocket_service
from .api import 数据上传接口, 插值任务接口, 结果查询接口, 任务状态接口, 报告生成接口, 模型推荐接口, 采样建议接口, 采样点影响评估接口, 行业配置接口, 批量插值接口, 参数批量应用接口, 结果对比分析接口, 批量报告生成接口, 进度详情接口, 资源监控接口, 任务队列接口, 性能报告接口, 不确定性分级接口, 风险指数接口, 决策阈值接口, 风险报告接口, 异常检测接口, 误差预测接口, 模型评估接口, 配置接口, 路径规划接口, 模型融合接口, 项目管理接口, 通用数据处理接口, 数据质量接口, GPU加速接口, 数据反馈接口, 主动学习接口, 用户验证与自评估接口, 移动端GPS接口, 历史对比与趋势分析接口
from .api.app_download_api import router as download_router
from .api.admin_api import router as admin_router
from .api.auth_api import router as auth_router
from .api.company_management_api import router as company_management_router
from .api.devices_api import router as devices_router
from .services.mobile_gps_service import mobile_gps_service

# 导入新增的系统路由
from realtime_interpolation.api import fastapi_routes as realtime_routes
from multi_objective_optimization.api import fastapi_routes as multi_objective_routes
from .kriging_3d.api.路由 import router as kriging_3d_router
from .dl_services.api import router as deep_learning_router
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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
app.include_router(性能报告接口.router, prefix="/api", tags=["性能报告"])
app.include_router(历史对比与趋势分析接口.router, prefix="/api", tags=["历史对比与趋势分析"])
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
app.include_router(数据反馈接口.router, prefix="/api", tags=["数据反馈"])
app.include_router(主动学习接口.router, prefix="/api", tags=["主动学习与半监督"])
app.include_router(用户验证与自评估接口.router, prefix="/api", tags=["用户验证与模型自评估"])
app.include_router(GPU加速接口.router, prefix="/api", tags=["GPU加速"])
app.include_router(移动端GPS接口.router, tags=["移动端GPS"])
app.include_router(download_router, prefix="/api", tags=["下载"])
app.include_router(auth_router, prefix="/api", tags=["认证"])
app.include_router(devices_router, prefix="/api", tags=["设备管理"])
app.include_router(company_management_router, prefix="/api", tags=["企业管理"])
app.include_router(admin_router, prefix="/api", tags=["管理员后台"])

# 注册新增的系统路由
app.include_router(realtime_routes.router, prefix="/api", tags=["实时插值"])
app.include_router(multi_objective_routes.router, prefix="/api", tags=["多目标优化"])

# 注册3D克里金路由
app.include_router(kriging_3d_router, prefix="/api", tags=["3D克里金"])

# 注册深度学习路由
app.include_router(deep_learning_router, prefix="/api", tags=["深度学习"])


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
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket_service.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            await handle_websocket_message(client_id, data)
    except WebSocketDisconnect:
        websocket_service.disconnect(client_id)

async def handle_websocket_message(client_id: str, message: dict):
    message_type = message.get('type')
    message_data = message.get('data') or {}
    message_id = message.get('message_id') or message_data.get('message_id')

    if message_type == 'subscribe_task':
        task_id = message.get('task_id') or message_data.get('task_id')
        await websocket_service.subscribe_to_task(client_id, task_id)
        await websocket_service.send_personal_message({
            'type': 'subscription_confirmed',
            'task_id': task_id
        }, client_id)

    elif message_type == 'unsubscribe_task':
        task_id = message.get('task_id') or message_data.get('task_id')
        await websocket_service.unsubscribe_from_task(client_id, task_id)
        await websocket_service.send_personal_message({
            'type': 'unsubscription_confirmed',
            'task_id': task_id
        }, client_id)

    elif message_type == 'subscribe_gps_project':
        project_id = message.get('project_id') or message_data.get('project_id') or 'default_mobile_project'
        await websocket_service.subscribe_to_project(client_id, project_id)
        await websocket_service.send_personal_message({
            'type': 'subscription_confirmed',
            'project_id': project_id,
            'message_id': message_id
        }, client_id)

    elif message_type == 'unsubscribe_gps_project':
        project_id = message.get('project_id') or message_data.get('project_id') or 'default_mobile_project'
        await websocket_service.unsubscribe_from_project(client_id, project_id)
        await websocket_service.send_personal_message({
            'type': 'unsubscription_confirmed',
            'project_id': project_id,
            'message_id': message_id
        }, client_id)

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
        await websocket_service.send_personal_message({
            'type': 'ack',
            'message_id': message_id,
            'data': result,
            'timestamp': datetime.now().isoformat()
        }, client_id)

        if result.get('applied_samples'):
            for applied in result['applied_samples']:
                await websocket_service.notify_gps_update(
                    project_id=project_id,
                    sample=applied,
                    exclude_client_id=client_id
                )

    elif message_type in {'gps_ping', 'ping'}:
        await websocket_service.send_personal_message({
            'type': 'gps_pong' if message_type == 'gps_ping' else 'pong',
            'message_id': message_id,
            'timestamp': datetime.now().isoformat()
        }, client_id)

    elif message_type == 'ack':
        ack_id = message_data.get('message_id') or message_data.get('id') or message_id
        if ack_id:
            await websocket_service.confirm_ack(client_id, ack_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
