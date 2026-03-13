"""
FastAPI主应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .api import 数据上传接口, 插值任务接口, 结果查询接口, 任务状态接口, 报告生成接口, 模型推荐接口, 采样建议接口
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="基于克里金插值的空间不确定性分析平台"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/results", StaticFiles(directory=str(settings.RESULTS_DIR)), name="results")

# 注册路由
app.include_router(数据上传接口.router, prefix="/api", tags=["数据上传"])
app.include_router(插值任务接口.router, prefix="/api", tags=["插值任务"])
app.include_router(结果查询接口.router, prefix="/api", tags=["结果查询"])
app.include_router(任务状态接口.router, prefix="/api", tags=["任务状态"])
app.include_router(报告生成接口.router, prefix="/api", tags=["报告生成"])
app.include_router(模型推荐接口.router, prefix="/api", tags=["模型推荐"])
app.include_router(采样建议接口.router, prefix="/api", tags=["采样建议"])

@app.get("/")
async def root():
    return {
        "message": "智能不确定性驱动空间决策平台",
        "version": settings.VERSION,
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
